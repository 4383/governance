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

"""Build a table of the current members of the TC.
"""

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst.directives import tables
from docutils.utils import SystemMessagePropagation
from sphinx.util import logging

from openstack_governance import projects

LOG = logging.getLogger(__name__)


class TCLiaisonsTable(tables.Table):
    """Insert the members table using the referenced file as source.
    """

    HEADERS = ('TC Member', 'Projects')

    option_spec = {'class': directives.class_option,
                   'name': directives.unchanged,
                   'datafile': directives.unchanged,
                   }

    has_content = False

    def run(self):
        env = self.state.document.settings.env

        # The required argument to the directive is the name of the
        # file to parse.
        datafile = self.options.get('datafile')
        if not datafile:
            error = self.state_machine.reporter.error(
                'No filename in membertable directive',
                nodes.literal_block(self.block_text, self.block_text),
                line=self.lineno)
            return [error]

        # Handle the width settings and title
        try:
            col_widths = self.get_column_widths(len(self.HEADERS))
            title, messages = self.make_title()
        except SystemMessagePropagation as detail:
            return [detail.args[0]]
        except Exception as err:
            error = self.state_machine.reporter.error(
                'Error processing memberstable directive:\n%s' % err,
                nodes.literal_block(self.block_text, self.block_text),
                line=self.lineno,
            )
            return [error]

        # Now find the real path to the file, relative to where we are.
        rel_filename, filename = env.relfn2path(datafile)

        # Build the table node using the parsed file
        data_iter = projects.load_project_file(filename)
        liaisons = {}
        for project_name, project in data_iter.items():

            for liaison in project.get('liaisons', []):
                try:
                    liaisons[liaison].extend([project_name])
                except KeyError:
                    liaisons[liaison] = []
                    liaisons[liaison].extend([project_name])

        table_node = self.build_table(
            liaisons,
            col_widths,
        )
        table_node['classes'] += self.options.get('class', [])
        self.add_name(table_node)

        if title:
            table_node.insert(0, title)

        return [table_node] + messages

    def build_table(self, table_data, col_widths):
        table = nodes.table()

        # Set up the column specifications
        # based on the widths.
        tgroup = nodes.tgroup(cols=len(col_widths))
        table += tgroup
        tgroup.extend(nodes.colspec(colwidth=col_width)
                      for col_width in col_widths)

        # Set the headers
        thead = nodes.thead()
        tgroup += thead
        row_node = nodes.row()
        thead += row_node
        row_node.extend(
            nodes.entry(h, nodes.paragraph(text=h))
            for h in self.HEADERS
        )

        # The body of the table is made up of rows.
        # Each row contains a series of entries,
        # and each entry contains a paragraph of text.
        tbody = nodes.tbody()
        tgroup += tbody
        rows = []
        for member, tc_projects in table_data.items():
            trow = nodes.row()
            # Iterate over the headers in the same order every time.
            name = nodes.entry()
            name += nodes.paragraph(text=str(member))
            trow += name
            project = nodes.entry()
            project_list = nodes.paragraph()
            for proj in tc_projects:
                project_list += nodes.reference(
                    proj, proj, refuri="projects/%s.html" % proj)
                project_list += nodes.Text(", ")
            project += project_list
            trow += project
            rows.append(trow)
        tbody.extend(rows)

        return table


def setup(app):
    LOG.info('loading tc liaisons extension')
    app.add_directive('liaisonstable', TCLiaisonsTable)
