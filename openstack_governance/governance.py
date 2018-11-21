#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Work with the governance repository.
"""

import weakref

from openstack_governance import yamlutils

import requests

PROJECTS_LIST = "http://git.openstack.org/cgit/openstack/governance/plain/reference/projects.yaml"  # noqa
TC_LIST = "http://git.openstack.org/cgit/openstack/governance/plain/reference/technical-committee-repos.yaml"  # noqa
SIGS_LIST = "http://git.openstack.org/cgit/openstack/governance/plain/reference/sigs-repos.yaml"  # noqa


def get_tags_for_deliverable(team_data, team, name):
    "Return the tags for the deliverable owned by the team."
    if team not in team_data:
        return set()
    team_info = team_data[team]
    dinfo = team_info['deliverables'].get(name)
    if not dinfo:
        return set()
    return set(dinfo.get('tags', [])).union(set(team_info.get('tags', [])))


class Team(object):

    def __init__(self, name, data):
        self.name = name
        self.data = data
        # Protectively initialize the ptl data structure in case part
        # of it is missing from the project list, then replace any
        # values we do have from that data.
        self.ptl = {
            'name': 'MISSING',
            'irc': 'MISSING',
        }
        self.ptl.update(data.get('ptl', {}))
        self.deliverables = {
            dn: Deliverable(dn, di, self)
            for dn, di in self.data.get('deliverables', {}).items()
        }

    @property
    def tags(self):
        return set(self.data.get('tags', []))


class Deliverable(object):
    def __init__(self, name, data, team):
        self.name = name
        self.data = data
        self.team = weakref.proxy(team)
        self.repositories = {
            rn: Repository(rn, self)
            for rn in self.data.get('repos', [])
        }

    @property
    def tags(self):
        return set(self.data.get('tags', [])).union(self.team.tags)


class Repository(object):
    def __init__(self, name, deliverable):
        self.name = name
        self.deliverable = weakref.proxy(deliverable)

    @property
    def tags(self):
        return self.deliverable.tags


class Governance(object):

    def __init__(self, team_data, tc_data, sigs_data):
        self._team_data = team_data
        self._tc_data = tc_data
        self._sigs_data = sigs_data

        team_data['Technical Committee'] = {
            'deliverables': {
                repo['repo'].partition('/')[-1]: {'repos': [repo['repo']]}
                for repo in tc_data['Technical Committee']
            }
        }
        for sig_name, sig_info in sigs_data.items():
            team_data['{} SIG'.format(sig_name)] = {
                'deliverables': {
                    repo['repo'].partition('/')[-1]: {'repos': [repo['repo']]}
                    for repo in sig_info
                }
            }

        self._teams = [Team(n, i) for n, i in self._team_data.items()]

    @classmethod
    def from_urls(cls,
                  team_url=PROJECTS_LIST,
                  tc_url=TC_LIST,
                  sigs_url=SIGS_LIST):
        r = requests.get(team_url)
        team_data = yamlutils.loads(r.text)
        r = requests.get(tc_url)
        tc_data = yamlutils.loads(r.text)
        r = requests.get(sigs_url)
        sigs_data = yamlutils.loads(r.text)
        return cls(team_data, tc_data, sigs_data)

    def get_repo_owner(self, repo_name):
        """Return the name of the team that owns the repository.

        :param repo_name: Long name of the repository, such as 'openstack/nova'.

        """
        for team, info in self._team_data.items():
            for dname, dinfo in info.get('deliverables', {}).items():
                if repo_name in dinfo.get('repos', []):
                    return team
        raise ValueError('Repository %s not found in governance list' % repo_name)

    def get_repositories(self, team_name=None, deliverable_name=None,
                         tags=[]):
        """Return a sequence of repositories, possibly filtered.

        :param team_name: The name of the team owning the repositories. Can be
            None.
        :para deliverable_name: The name of the deliverable to which all
           repos should belong.
        :param tags: The names of any tags the repositories should
            have. Can be empty.

        """
        if tags:
            tags = set(tags)

        if team_name:
            try:
                teams = [Team(team_name, self._team_data[team_name])]
            except KeyError:
                raise RuntimeError('No team %r found in %r' %
                                   (team_name, list(self._team_data.keys())))
        else:
            teams = self._teams

        for team in teams:
            if deliverable_name and deliverable_name not in team.deliverables:
                continue
            if deliverable_name:
                deliverables = [team.deliverables[deliverable_name]]
            else:
                deliverables = team.deliverables.values()
            for deliverable in deliverables:
                for repository in deliverable.repositories.values():
                    if tags and not tags.issubset(repository.tags):
                        continue
                    yield repository