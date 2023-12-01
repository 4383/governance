==================================
Migrate Eventlet Usages to Asyncio
==================================

Problem
=======

Openstack is build on the top of asynchronous mechanisms.

All the Openstack components heavily relies on the Eventlet library to
obtain asynchronous features, however, the Openstack community currently
suffer from many aspects of the usage of that library.

Indeed this library currently do not support Python 3.12 and face many issues
with Python 3.11 (those are described below).

This new python version will be part of the supported runtime in the coming
Openstack series. At least Python 3.12 should be a supported runtime of the
"Dalmatian" series. 2024.1/Caracal currently `support Python 3.11 <https://governance.openstack.org/tc/reference/runtimes/2024.1.html>`_.

Many distros already started to transition to Python 3.12. That's the
case for Debian, Fedora `includes all Python versions <https://developer.fedoraproject.org/tech/languages/python/multiple-pythons.html>`_
which are `supported upstream <https://devguide.python.org/versions/#versions>`_,
and Ubuntu 24.04 `also introduced support to this version <https://launchpad.net/ubuntu/noble/+package/python3-all>`_.

It is urgent to solve this compatibility problem and it could be the right
moment to move to a more sustainable solution in replacement of Eventlet.
Without rapid actions the community will soon face more pressure.

Here is a purged list of the main pain points in Eventlet that led to this
situation:

#. **The lack of maintenance:** the lib is not actively maintained. No reviews
   were made during several months. Only one person could be still considered
   as an active core member. The consequences of this inactivity are legion.
   Tests don't pass, locally or in CI. CI doesn't run at all for Python 3.11.
   The github pull requests and issues backlogs of Eventlet are growing
   indefinitely. Legit bug are not fixed. Python 3.12 is not supported in
   runtime.

#. **The technological dead-end:** The premise of Eventlet is drop-in
   compatibility via monkey patching. Unfortunately that quite possibly hasn't
   been true for a long time, and it's becoming increasingly more difficult
   over time and over new Python version.

   *Example #1: Compliance suite*

   Per `the docs <https://github.com/eventlet/eventlet/blob/master/doc/testing.rst#standard-li>`_,
   "Eventlet provides the ability to test itself with the
   standard Python networking tests. This verifies that the libraries it wraps
   work at least as well as the standard ones do."

   That is, Eventlet will run the Python standard library's test suite against
   Eventlet to make sure it's compatible.

   Unfortunately, this testing mechanism was never updated for Python 3.

   As such, it's basically designed for Python 2.7, and there has been 13
   major releases of Python since then. Is Eventlet still compatible with the
   standard library? It's hard to say, but quite likely not.

   *Example #2: RLock*

   When Eventlet was originally written, ``threading.RLock`` was written in
   Python. This has a bug, e.g. it didn't actually work in the face of
   signals: https://bugs.python.org/issue13697 (there's a bunch of comments in
   the ticket from people encountering this in the real world, logging being a
   common situation.)

   The problem doesn't occur in the version of RLock which is written in C,
   which is the current default and was introduced in Python 3.2.

   However, the C version of RLock doesn't work with Eventlet, so Eventlet has
   been monkey patching ``threading.RLock``, replacing it with the (buggy and
   unfixable) version written in Python (``threading._PyRLock_``).

   In 3.11 this gets worse, as the RLock version written in Python has become
   subtly incompatible with eventlet's expectations. To get the Eventlet test
   suite passing on 3.11 maintainers had to copy/paste the Python RLock code
   and `tweak
   it <https://github.com/eventlet/eventlet/pull/823/files#diff-029df1ae9b7431e9cdd>`_.

   So now Eventlet has to use a forked version of a broken implementation of
   RLock. It's possible there's another solution, but Eventlet basically
   relies on monkey patching a whole bunch of functions and on implementation
   details of Python standard library using those functions in particular ways,
   which are not always stable over time.

   This problem will continue to get worse as Python evolves. E.g. it would
   not surprise if the GIL removal makes things even more difficult for
   Eventlet.

Root Cause
==========

One could think that the root cause of the Openstack issue described above
lives in the recent lack of maintenance of the Eventlet library, yet this is
not the case. Even if Eventlet simplified the life of the community developers
for years, one can't ignore the fact that by its inherent philosophy and nature
it has only widened the gap between the Openstack code base and the CPython
stdlib implementation.

Now, because of the usage of Eventlet, 13 major releases of CPython implicitly
separate Openstack and CPython.

Thinking that the recent lack of maintenance in Eventlet explain our current
issue and hoping that simply fixing two or three things will unlock our
problem is just hypothetical. When the `GIL removal (for now just optional) <https://peps.python.org/pep-0703/>`_
will become a reality we will surely live in a nightmare.

Indeed, considering that Eventlet is fully based on volunteers, and
considering the current available resources of this project - 3 people -, it
would be feasible to fix urgent things, but considering the gap between
Eventlet and the recent CPython releases, it would be really hard to catch up
and it would surely require several development years.

So, for these reasons, thinking that way will sooner lead us toward deeper
moats which are impossible to cross. Thinking that way already led us to stick
to EOLed design of CPython.

One could think that the Eventlet case is an isolated case. Unfortunately not.
Resources are scarce. The same observation is true for the
vast majority of other third parties libraries. Almost all these
libraries rest on the shoulders of one or two people. It's the harsh law of
the open source ecosystem. Scarcity lead the world. Only mainstream projects
like CPython or Openstack has decent resources. Winners take all.

The root cause of the problems described here is due to the fact of using
a library without resources. A library that did not have the means to adapt
to its environment. A library designed to solve Python design issues from
another time. A time when python was not provided with an internal
asynchronous backend.

All the problems described above inherit from choices made in Eventlet, several
years ago, to improve older versions of Python, 2.7 at least. All the current
issues are related to Eventlet design implementations made for Python EOL
versions. Design choices and implementation made at a time where the Python
stdlib was not designed to support async. That mean that Openstack is now
really far from the concurrency approach chosen by our main runtime, Python.
An approach that is the future of the main technology on which rest all
Openstack, Python.

Even if Python 2.7 is now EOL and even if its support have been dropped from
Openstack years ago, today we are still impacted by previous design choices
made for it.

One major argument initially brandished to defend usage of Eventlet inside
Openstack was one of those was to avoid explicit concurrency in our code base.
Monkey patching. We use Eventlet as an optional, pluggable, backend that allows
swapping out blocking APIs for an event loop, transparently, without changing
any code. However, with time, this affirmation has become false. Now,
`numerous are the examples where Openstack source code now has a whole bunch
of patches necessary for Eventlet to work properly
<https://codesearch.openstack.org/?q=is_monkey_patched&i=nope&literal=nope&files=&excludeFiles=&repos=>`_.
`Locks are heavily used in sync designed Openstack code
<https://codesearch.openstack.org/?q=self.lock%3A&i=nope&literal=nope&files=&excludeFiles=&repos=>`_
, where, apparently, no explicit concurrency is expected. Eventlet has
infected synchronous code. Even our initial arguments have evaporated with
time.

Is all this Eventlet problem are solvable? Is the gap recoverable?
Yes, but at a significant cost.

Investing money, time, and engineering skills in a solution that will continue
to diverge from the main runtime pillar of Openstack, Python, isn't something
conceivable.

Investing energy in a solution that is made to improve dead version of Python
is not something rational.

Investing Openstack's precious - decreasing - resources in a migration toward
one an other library likes Eventlet, without it having good and long term
maintenance capabilities is not something desirable neither. We would face the
same situation again, sooner than we think.

The current situation, trigger a signal to the community. The community should
catch this event to decide actions to lead Openstack toward a solution.
A realistic solution. A pragmatic solution. A deterministic solution.

We should design a solution, that once is applied, must ensure that the
current inputs always provides the same outputs. No regressions.

Sustainability should be the main priority of the Openstack community.
Our sustainability should be based on the future of Python, not on its past.

For that reason this community goal proposal will try to propose actions in,
short, medium, and long terms, to move Openstack in the right direction in
the aim of solving the current issues and also to prevent from similar
situation again in the future of Openstack.

Eventlet is not a sustainable solution for a project like Openstack. Eventlet
struggles to remain compatible with CPython. Using Eventlet introduce
a gap between us and the CPython stdlib. The solution below aim to
remove that gap.

If one think that all the previously described pain points are acceptable then
continuing using a poorly maintained Eventlet is also acceptable, and the
solution below could be ignored.

Solution
========

This proposal aim to make Eventlet work again on the short run.
Then incrementally abandon Eventlet in favor of Asyncio to keep Openstack
healthy on the long run.

The proposed solution focus exclusively on Openstack components that
currently relies on Eventlet. The purpose of Eventlet is to manage
asynchronism and coroutines. Feature who were absent from the stdlib.
Eventlet, at the time of its invention, did that by
relying on threads. Today, in 2024, the CPython stdlib, includes
coroutines and async features - Asyncio. The purpose of Asyncio is
the same that Eventlet .We propose to use Asyncio to replace Eventlet where it
is currently used.

Some may ask, why using Asyncio and not simply using threads and parallelism?
Threading - as a programming model - is best suited to certain
kinds of computational tasks that are best executed with multiple CPUs and
shared memory for efficient communication between the threads. In such tasks,
the use of multicore processing with shared memory is a necessary evil because
the problem domain require it. Network programming is not one of those
domains. The key insight is that network programming involves a great deal of
"waiting for things to happen" and because of this, we don't need the
operating system to efficiently distribute our tasks over multiple CPUs.
Furthermore, we don't need the risks that preemptive multitasking brings, such
as race conditions when working with shared memory.

Parallelism is when tasks literally run at the same time, e.g., on a multicore
processor. On the paper `Threads are made for parallelism <https://docs.python.org/3/library/threading.html#module-threading>`_,
not for concurrency, but, in CPython, the GIL affect threading.
`One thread runs Python, while N others sleep or await I/O <https://wiki.python.org/moin/GlobalInterpreterLock>`_.
When do threads switch? Whenever a thread begins sleeping or awaiting network
I/O, there is a chance for another thread to take the GIL and execute Python
code, not really such a parallelism. The GIL prohibits parallelism with
threads. Only multiple processes (forks) would allow real parallelism with
CPython.

Threads consume a lot of preallocated virtual memory per thread (8Mb stack
space per thread), that's not the case of Asyncio. Threads requires context
switching even when threads are waiting from an IO, Asyncio not. At very high
concurrency levels, there can also be an impact on throughput due to `context
switching costs <https://blog.tsunanet.net/2010/11/how-long-does-it-take-to-make-context.html>`_.
Threads are resources intensive and not particularly designed for non blocking
IO.

In Linux, everything is file, so sockets are files.
Each Linux machine define a maximum number of file descriptors allowed to be
opened simultaneously, example on my laptop:

.. code-block::

    $ cat /proc/sys/fs/file-max
    9223372036854775807

Also Linux have a limit on the total number of processes on the system:

.. code-block::

    $ cat /proc/sys/kernel/threads-max
    254428

This number can be increased, but, the preallocated virtual memory per thread
is not infinite.

So, the number of possible threads in the same time is significantly lower
than the number of sockets connections that can be made within the same OS.
Using threads to handle sockets, would significantly limit the number of
possible connections we could made.

On the contrary, asyncio is a module made to write concurrent code.
Concurrency is when two or more tasks can start, run, and complete in
overlapping time periods. It doesn't necessarily mean they'll ever both be
running at the same instant. Asyncio is not affected by the GIL, but it cannot
benefit from multiple CPU either. In Asyncio each task decide to when get back
control to the main event loop. Asyncio coroutines avoid context switching.
Asyncio save system resources.

In short, Asyncio offers:
* a safer alternative to preemptive multitasking.
* a simple way to support many thousand of simultaneous socket connections.

Replacing Eventlet with native threads just because Eventlet's choice of async
programming model is threads doesn't mean we need to move to it.

By replacing features of Eventlet by features specifically tailored for
network IO from the CPython stdlib, we would benefit from the right feature at
the right place.

We would also benefit from the sustainability and the stability
offered by CPython. In the past, we made a wise choice trusting the CPython
stability to built Openstack. A choice which has proved its worth. A choice
that made Openstack the mature project it is today. Our position as leader in
cloud computing confirm that fact. Using Asyncio is coherent with our
previous decisions.

CPython is `sponsored by major industries companies <https://www.python.org/psf/sponsors/>`_.
By using Asyncio, we would also benefit from all the contributions, all
the skills, and all resources of the CPython and the PSF community.
Resources which are not comparable to the resources available to Eventlet or
to any other third parties libraries (e.g gevent, greenlet, etc).

As the future of Python is public, well planned, and accessible through PEP
mechanisms, ultimately, this solution would also give a more clearer vision
of the future of the async model of Openstack. A future that would rest on a
sustainable background.

Not all Openstack components use Eventlet but many of them heavily relies on
this library. Eventlet manage async and coroutines by using monkey patching
and green threads/pools. Replacing Eventlet usages by asyncio, would mean
managing async code without necessarily using threads. Hence, this migration
would require a design refactor for these Openstack components.

The solution described here propose to smoothly migrate from a broken
Eventlet, to a functional asyncio. All of that would be possible by keeping
Eventlet healthy in the short run.

The solution propose 3 global milestones, short, medium, and long term, and
plan to try to define how to migrate a single deliverable. Those plans
are described in the following sections.

The global duration of this goal could be at least five to six years and
would requires several series to be fully applied.

Removing Eventlet is not an option. That's a vital need.

Short terms solutions
~~~~~~~~~~~~~~~~~~~~~

As Python 3.12 will be a supported runtime in the next coming
Openstack series, the support issue should be quickly fixed.

So, In short terms Eventlet itself should be fixed first.

This milestone should be done before the beginning the next series
("2024.2/Dalmatian").

Firstly we would have to fix `the broken CI problems <https://github.com/eventlet/eventlet/actions>`_
and hence ensure that submitted patches (bug fixes, features, etc) could be
also merged without being block by a failing CI. Development workflow should
be secured first.

Secondly, once gates would be fixed, it would be possible to fix the SSL issue
and so to support Python 3.12. That would be possible by fixing
`this existing issue <https://github.com/eventlet/eventlet/issues/795>`_.

The good news is that patches fixing problems have been already proposed:
* The broken CI (https://github.com/eventlet/eventlet/pull/823).
* The broken support of Python 3.12 (https://github.com/eventlet/eventlet/pull/817)

The main problem for the Openstack community, with these patches, is now to
see them merged in time to match the Openstack calendar.

A `discussion have been started <https://github.com/eventlet/eventlet/issues/824>`_
between us and historical maintainers of Eventlet.

The goal of this discussion was to see if maintainers would agree to
grant access to Openstack developers who would volunteer to maintain Eventlet.
Fortunately they agreed and grant access to some of us, and in addition they
also granted access to the Eventlet at three other significant and
historical Eventlet contributors.

So, we can seriously think that these patches could be merged in the coming
weeks.

Here is a plan proposal to see this milestone succeed:

#. Start the discussion with current maintainers (done).
   https://github.com/eventlet/eventlet/issues/824

#. gain write access to the current repo (done).
   https://github.com/eventlet/eventlet/issues/824#issuecomment-1853128741

#. draft future announcements early in the process to ensure we have achieved
   our goals when the time comes to publish our announcements. Could be
   a good benchmark for us to measure our advancements and to validate them.

#. Merge the CI patches. (done)
   * https://github.com/eventlet/eventlet/pull/827
   * https://github.com/eventlet/eventlet/pull/831
   * https://github.com/eventlet/eventlet/pull/832

#. Merge the fix for introduce the support of Python 3.12. (done)
   * https://github.com/eventlet/eventlet/pull/817
   * https://github.com/eventlet/eventlet/pull/847
   * https://github.com/eventlet/eventlet/pull/854

#. Release the latest changes by creating a new version. (done)
   * https://github.com/eventlet/eventlet/issues/842
   * https://github.com/eventlet/eventlet/issues/861
   * https://pypi.org/project/eventlet/0.34.1/
   * https://pypi.org/project/eventlet/0.34.2/

#. Upgrade the Openstack requirements to match this new version. (done)
   * https://review.opendev.org/c/openstack/requirements/+/904147
   * https://review.opendev.org/c/openstack/requirements/+/907048

#. Validate that the main issues are now fixed. (in progress)

#. Announce the current state of the art after the previous steps are done.
   The goal would be to offer visibility to Openstack maintainers.

#. (optional) Decide with the TC to postpone the support of Python 3.12 within
   the next series ("D") if the validation failed and if we are to close from
   the deadline. Socialize that point to the community. This is a possible way
   out that we must still avoid at all costs.

#. (optional) If we previously postponed the support of Python 3.12 due to
   validation issue, see what happens and try to fix it during "D".


Medium terms solutions
~~~~~~~~~~~~~~~~~~~~~~

At this stage, Eventlet could be considered as healthy and Openstack secured
for the coming series.

As our goal is to move to asyncio, and as Eventlet occupies an important place
in Openstack, we would have to consider a couple of points:

#. Without some configuration, Eventlet and `Asyncio are not compatible and
   can't live together in the same process <https://github.com/eventlet/eventlet/issues/673#issuecomment-740429872>`_.
   So, the migration should start by applying this configuration first.

   Allowing running Eventlet and Asyncio in the same process will allow us a
   gradual migration. A gradual migration would leave some room to team to
   breath and to continue supporting the usual affairs of their deliverables.

#. One thing that might be worth calling out is that Eventlet provides
   greenthreads which run in a way that feels preemptive even if in a way they
   are cooperative by calling into monkey patched code paths that allow for
   context switches. On the other hand asyncio tends to be very cooperative.

   Moving away from Eventlet to asyncio is more than what library do you
   choose to use; the entire approach to concurrency differs.

   For this reason, this move would potentially also require a
   rewrite/refactor of applications to handle the logical change in control
   flow that happens as a result.

#. Again, in the Openstack context, Eventlet is mostly used as an optional,
   pluggable, backend that allows swapping out blocking APIs for an event
   loop, transparently, without changing any code. This behavior allow us to
   call the same code in all our services, no matters if these
   services needs to behave synchronously or asynchronously and no matter
   if they needs to call async or non-async code.

   However, as seen previously, Asyncio, doesn't behave that way.
   By using Asyncio, callers of an async code should be also adapted to
   become async. The way Asyncio is designed, does not offer a way to schedule
   async call from a non-async code and get a response.
   If we are not careful, using Asyncio could contaminate every pieces of
   Openstack, even if these piece are not using Eventlet at all. By using
   Asyncio without considering that point would engage us in a more biggest
   refactor that the one initially requested by this goal.

   Services who are not using Eventlet should not be impacted by this
   proposal. Fortunately, it exists patterns that could allow us to implement
   Asyncio in our code base, without requesting adaptation from the
   synchronous callers. These patterns will be described later in this
   document.

   The same affirmation is also true for all our dependencies. As Eventlet
   monkey patch all the running stack, all our dependencies are also
   monkey patched, so, as our goal is to migrate our services and our
   libraries, and as they relies on third parties requirements, we also have
   to identify async candidates to replace external sync requirements that are
   monkey patched and that we currently uses. If one is not replaceable, then,
   wrap the existing one into async/sync patterns (described later in this
   document).


This milestone would surely require at least two series. One series
(2024.2/Dalmatian) to design and implement the transitive engine that
will allow us to start the migration and two series (2025.2/F) to migrate the
first bricks. Here are items for milestone 2:

#. design specs of the new Eventlet's Asyncio hub or similar that has an
   asyncio backed eventloop that we can enable instead of the default Eventlet
   one. (done)

   * https://github.com/eventlet/eventlet/issues/868

#. implementing the new hub. (done)

   * https://github.com/eventlet/eventlet/issues/869
   * https://eventlet.readthedocs.io/en/latest/migration.html#migration-guide

#. Upgrade the minimal version of Eventlet in ``requirements.txt`` files of
   deliverables using Eventlet. As libraries would be transitioned first, and
   as they will have to relies on Asyncio, we would have to always use
   Eventlet in a compatible version (at least `0.35.0 <https://github.com/eventlet/eventlet/releases/tag/v0.35.0>`_).
   So we would have to force this minimal version in all the deliverables that
   relies on Eventlet.

   Acting this way will also avoid pip resolver conflicts
   related to different versions Eventlet between deliverables. Some
   deliverables are defining Eventlet in their ``requirements.txt`` some other
   in their ``test-requirements.txt`` and only for testing purpose. Enforcing
   the minimal version of Eventlet everywhere would reduce the chances of
   broken gates and hence, would reduce the pain of the migration.

#. Identify and add replacement third parties libraries into
   ``openstack/requirements``. It exists good candidates replacement for almost
   all our third parties libraries. `Here is curated list
   <https://github.com/timofurrer/awesome-asyncio>`_
   that can help us which package we want to use for depending on our needs.

   Once selected these packages should be added, one by one, to
   ``openstack/requirements``, `by following our usual process
   <https://docs.openstack.org/project-team-guide/dependency-management.html#for-new-requirements>`_.

#. `Activate the new Eventlet Asyncio hub <https://eventlet.readthedocs.io/en/latest/migration.html#step-1-switch-to-the-asyncio-hub>`_
   on every Openstack deliverables that relies on Eventlet. This will allow to
   run Eventlet and asyncio code in the same process. From this point, we will
   be able to start refactor our own code to migrate async features toward
   Asyncio. As `the Asyncio hub was added within Eventlet 0.35.0 <https://github.com/eventlet/eventlet/releases/tag/v0.35.0>`_,
   this will require Eventlet in a version equal or higher to version 0.35.0.

#. migrate to Asyncio the first Openstack bricks (a couple of identified
   libraries):
   * oslo.service;
   * oslo.messaging;
   * oslo.concurrency;
   * OpenstackSDK (SDK is blocking and do not support async, it should be also migrated to asyncio to avoid wrapping rest calls made to other services)

   All these libraries are blocking and are the perfect example of monkey
   patched code that, by default, do not support async.

   These deliverables heavily relies on Eventlet and their design are
   tiddly coupled to this library, so moving them first would be a first
   significant step toward a successful migration.

   For more details about how to conduct a migration for a single deliverable
   please see :ref:`how-to-migrate-our-deliverables`.

#. choose a service that will serve as reference user. Glance-api have been
   proposed because it seems relatively small and typical.

#. migrate this reference user deliverable (glance-api for now).

#. prepare a migration guide based on the observations made during the
   migration of the previous deliverables. The goal of this guide would be
   to help during the migration of the services and of the libraries that
   remains not transitioned. This guide should accelerate the way teams are
   able to migrate their deliverables.

#. cross testing the previously migrated deliverables. It would surely
   need the help of the QA team and of the requirements and infra team to
   design these cross tests and to make them running jobs.

#. identifying the low hanging fruits that could be easily migrated by
   involving cross team expertness to inspect their deliverables. That would
   help making a list of migration priority and give a big picture of the
   remaining workload.

Long terms solutions
~~~~~~~~~~~~~~~~~~~~

This milestone would surely require at least four or five series. 2027.2
would surely be our deadline.

Deliverables like nova or swift could be the hard ones to migrate.
Also we could face difficulty with non active deliverables. They could slow
down our progress.

Here are the main steps to conduct this long terms migration:

#. Identify deliverables who are not actively maintained and decide with the
   TC to retire them. This is a crucial point to avoid falling in an infinite
   loop of projects still relying on Eventlet and that could stuck this goal.

   This kind of deliverable could force us to rollbacks all our previous
   efforts as we did with the recent `oslo.db/sqlalchemy upgrade <https://lists.openstack.org/archives/list/openstack-discuss@lists.openstack.org/thread/Y4U2EHQYHB7DN5JSV2I7SJLXXVLW2QFF/#FMEIONXDKUKF3PXDULPFAVZ7WAGSTJIF>`_.
   We don't want to repeat this situation, especially with the inherent
   complexity of the Eventlet migration topic.

   Identifying them could be done with the help of release team and
   requirements team by defining some criteria like the absence of
   patches merged (excluding automated patches related to series upgrade) and
   the absence of new releases since more than 5 months from the beginning
   of the current series at this time.

#. Migrate all the Openstack remaining deliverables not yet migrated:
   * Remaining libraries should be migrated first.
   * Easily one should be migrated as soon as possible to allow harvesting
   feedback and experience easily acquired. The previously reference user
   (glance-api) could be used as an example.
   * Easily one should be migrated as soon as possible to free the maximum of
   available resources to focus efforts on the hardest deliverables to
   migrate.
   * Easily one should be migrated as soon as possible to allow cross
   integration testing to be run early during the migration of the
   hardest one.

   For more details about how to conduct a migration for a single deliverable
   please see :ref:`how-to-migrate-our-deliverables`.

#. Once all the deliverables are migrated, it would be time to retire the
   previously added Eventlet Asyncio Hub from every services because every
   Openstack pieces should be based on asyncio. At this point, and if not yet
   done, we should be able remove Eventlet requirements from all our
   deliverables.

#. Retiring third parties libraries from our global requirements. If a third
   party library is not used anymore (even in a non async/Eventlet model),
   then it could be removed from our global requirements. If all deliverables
   are already migrated, then all useless third parties requirements could
   be removed.

#. Once all the Openstack migration would be done we would have to Plan the
   retirement of Eventlet, or, at least, we would have to socialize the fact
   that we don't have anymore interest in continuing maintaining this library,
   so if the Openstack maintainers involved in Eventlet want to retire, then
   they would to socialize their departure. If someone else, outside of
   Openstack, volunteer to continue the Eventlet adventure, then, we would
   have to bequeath this project to him.

.. _how-to-migrate-our-deliverables:

How to migrate our deliverables
===============================

Here is a proposal to define the different required steps to migrate an
Openstack deliverable.

The Openstack Python code base is mostly composed of libraries and services.
The migration plan may differ depending the kind of deliverable.

In all the case the migration could be done directly the existing code base of
a repository by fully relying on the new Asyncio hub of Eventlet to manage the
cohabitation of Eventlet and asyncio in the same code base and in the same
stack.

We should notice that an incremental migration really increase the complexity
to get a big picture of the advancement of this goal. Almost all deliverables
relying on Eventlet could remains in a transient state without being fully
migrated to Asyncio. Migrating this way could lead us to a blur state.

How to migrate a library
~~~~~~~~~~~~~~~~~~~~~~~~

Consider the migration of a single one Openstack library (e.g oslo.messaging,
OpenstackSDK, ...). Lets call this Openstack library example ``oslo.demo``.
Migrating a library, in our example oslo.demo, would mean:

#. if not already done previously, starting by moving requirements of the
   oslo.demo, to a minimum version of Eventlet that support Asyncio (0.35.0 at
   least).

   Many libraries are requesting Eventlet in their ``test-requirements.txt``
   file. These requirements should be updated first to avoid pip resolver
   issues.

#. Identifying unused modules. Many of our libraries could own outdated, or
   even unused sub modules. It would be useless to spend time to transition
   them. These sub modules should be identified first, and then marked as
   deprecated. If not used elsewhere, a deprecated module won't be migrated.
   A deprecated module will be removed in a couple of cycles after its
   deprecation.

   If oslo.demo own unused or useless modules, then, these modules would be
   deprecated first. At this point it could be worth releasing a new version
   of oslo.demo before starting the migration.

#. Developers of the oslo.demo should identify which python packages could be
   good substitutes for the underlying IO libraries they are relying on.

   Example, the ``requests`` library could be replaced by the ``aiohttp``
   library.  Or, again, in an oslo.messaging context, the currently used
   `py-amqp <https://github.com/celery/py-amqp>`_ library could be replaced by
   `aioamqp <https://github.com/Polyconseil/aioamqp>`_

   It exists good candidates replacement for almost all our third parties
   libraries. `Here is curated list <https://github.com/timofurrer/awesome-asyncio>`_
   that can help us which package we want to use for depending on our needs.

   Identified candidates could be now added to the requirements of oslo.demo.

#. start migrating the code base of oslo.demo. Now that package
   substitutes have been selected we would be able to start migrating
   oslo.demo.

   By saying code base we mean only the code executed at runtime, not the unit
   tests. Unit tests, if possible, should be migrated in a second time, once
   the code base is fully migrated, to ensure that we have no regression and
   continue testing with tests designed before the migration.

   Suppose the following example. An Openstack hypothetical service relying on
   our fake and hypothetical oslo.demo library. Oslo.demo provide
   HTTP capabilities through a given client. In the following sample this
   oslo.demo is used to retrieve details of a specific VM instance by
   providing the VM identifier (`12345`) to an hypothetical rest API:

   .. code-block::

        from oslo_demo import Client

        client = Client()
        vm = client.request("https://api-rest.xyz/vm/12345")

   Here is an example of the hypothetical internal implementation of
   the oslo.demo ``Client`` class:

   .. code-block::

        import requests


        class Client():

            headers = {
                'User-Agent': 'sync_client',
            }

            def request(self, url):
                r = requests.get(url)
                return r.json()

   Considering how Openstack currently works, the service could be eager to
   execute this HTTP call in an asynchronous way. This service, by using
   Eventlet, could monkey patch all is stack at runtime. Then the request
   call would become async:

   .. code-block::

        import eventlet
        eventlet.monkey_patch()

        from oslo_demo import Client # non-blocking now

        client = Client()
        client.request(url)

   But oslo.demo could be also used the same way on services that do not
   rely on Eventlet, where blocking call are not a problem, or where the
   service manage async things internally by using threading or process,
   who know...

   oslo.demo is currently agnostic to network programming model used in its
   runtime environment. Environment defined by the service importing
   oslo.demo.

   Remember, we must migrate all our libraries in way where they remains
   compatible with all the network programming models used on services side.

   This where `the facade design pattern <https://en.wikipedia.org/wiki/Facade_pattern>`_
   can help us to implement blocking and non-blocking behaviors in all our
   libraries by only relying on a single design under the hood. Hence,
   everything would become based on Asyncio and coroutines but the facades
   will allow doing blocking IO calls by relying on an uniform async code
   base. 

   All services, even those not concerned by this migration, would be able
   to continue using our libraries. By doing things this way, these services
   won't be impacted by the migration. The migration would be transparent for
   them.

   Here is an example of what our previous oslo.demo code might look
   like once the migration is complete. This example implement the facade
   pattern introduced previously:

   .. code-block::

        import asyncio

        import aiohttp


        class AsyncClient():
            headers = {
                'User-Agent': 'async_client',
            }

            async def request(self, url):
                async with aiohttp.ClientSession(headers=self.headers) as session:
                    async with session.get(url) as response:
                        res = await response.json()
                        return res


        class Client(AsyncClient):

            def __init__(self):
                self.headers = {
                    'User-Agent': 'sync_client',
                }

            def _iter_coroutine(self, coro):
                loop = None
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    return loop.run_until_complete(coro)

            def request(self, url):
                return self._iter_coroutine(super().request(url))

   Migrated services would call the oslo.demo `Client.request` method like
   this:

   .. code-block::

        client = AsyncClient()
        asyncio.run(client.request(url))

   Or again like this:

   .. code-block::

        class ClassXYZ():
            def __init__(self):
                self.client = AsyncClient()


            async def feature_xyz(self):
                await self.client.request(url)

   Making explicit all the asynchronous calls of the service.

   `Here is a living PoC <https://github.com/4383/snippets/blob/main/python/facade/facade.py>`_
   more or less similar to this previous example.

   This proposal is inspired from the `edgedb-python <https://github.com/edgedb/edgedb-python>`_ library.
   Speaking examples of edgedb-python `usages are available here <https://www.edgedb.com/docs/clients/python/usage#edgedb-python-examples>`_.

   The migration of libraries should be incremental. We should transition them
   module by module. It would allow us to smoothly release migrated sub modules
   and then allow to expose them to library consumers (sometime libraries
   consumes other libraries, e.g oslo.utils, etc).

   Each new release of a migrated module would require at list a minor
   release.

#. Migrate unit tests. As said previously we want to
   avoid regression, so the latter we migrate unit tests the better.

#. Once a sub module will be fully transitioned, if its previous underlying
   library (e.g py-amqp), is not used elsewhere in this deliverable, then
   this requirement could be safely retired from the library.

#. oslo.demo would be considered as fully migrated once all its blocking IO
   underlying libraries would be retired from its requirements.

How to migrate a service
~~~~~~~~~~~~~~~~~~~~~~~~

As for libraries, the migration of services could be incremental.
As long as the Openstack libraries start releasing async sub modules and
features the services would be able to start using them.

Asynchronous support needs to be added down at the socket level, this is why
here we advocate to prefer the usage of asyncio compatible libraries, like by
example using `aiohttp` in-place of `requests`. the requests library uses
blocking calls throughout.

However, sometime that's could not possible to replace used libraries and
that's not possible to modify the code of these third parties libraries
either.

Possibly, services are more exposed to this kind of situation.
Fortunately it exist a way for services to use asyncio executors to
run blocking libraries things. For this reason, services developers would be
responsible of transforming their own code base to rely on asyncio executor
when blocking libraries are used in their code base, and, then,
become fully based on Asyncio (against, for services currently relying on
Eventlet).

As for the oslo.demo example, let's consider an hypothetical Openstack service
named `supernova`. Migrating a service like `supernova` would mean:

#. As a service migration could represent an heavy workload, and as Openstack
   resources are more decreasing than increasing, we recommend to split
   the transition into subtopics. Firstly we would recommend migrating one
   by one all usage of Openstack libraries to their async based facade.
   By example, in supernova, starting migrating oslo.messaging first, once
   done, start migrate oslo.cache, and so on. Then, once all Openstack library
   usages are transitioned then, start migrating third parties libraries calls
   directly made into supernova. The oslo.messaging migration is a subtopic.
   The oslo.cache migration is a subtopic. The migration of requests usages by
   aiohttp is a subtopic. And so on.

   requirements versions could be used to identify which subtopics remains
   an active topic or not - a transition to be made.

   We could maintains a requirements matrix helping to identify which
   versions of Openstack libraries are already migrated or not and maybe
   what is their level of migration completeness.

#. Updating supernova's requirements to the latest version of the library
   we want to migrate to async usage. Still corresponding to identified
   subtopics.

#. start migrating the code base of supernova. As for libraries we want to
   migrate the unit tests of supernova lastly, so this part of the migration
   is only about migrating the code base loaded at runtime, tests would be
   migrated in a second time.

   We would move from code like:

   .. code-block::

        import eventlet
        eventlet.monkey_patch()

        from oslo_demo import Client # non-blocking now

        client = Client()
        client.request(url)

   To something like:

   .. code-block::

        client = AsyncClient()
        asyncio.run(client.request(url))

   Or again like this:

   .. code-block::

        class ClassXYZ():
            def __init__(self):
                self.client = AsyncClient()


            async def feature_xyz(self):
                await self.client.request(url)

   In the case of a supernova subtopic related to direct usages of third party
   library (e.g `requests`) migration, developers would have either to replace
   this library by an async one (`requests` vs `aiohttp`), or, if it is not
   possible to replace it, then refactor code to call the blocking library
   into an executor, example with an hypothetical function, that is an
   asynchronous context manager that retrieve data by using `requests` and
   then continue to recording some stats access:

   .. code-block::

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def get_vm(id):
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, requests.get, f"https://api-rest.xyz/vm/{id}")
            yield data
            await loop.run_in_executor(
                None, record_access, id)

        async with get_vm("12345") as data:
            process(data)

   Services would also have to be adapted to starting up and shutting down
   gracefully. By example, service would have to provide a signal handler,
   to cancel tasks properly and control the life cycle of the event loop.
   Here is an implementation example:

   .. code-block::
       :caption: Example of Signal handling when using asyncio.run()

        import asyncio
        from signal import SIGINT, SIGTERM


        async def main():
            loop = asyncio.get_running_loop()
            for sig in (SIGTERM, SIGINT):
                # Because asyncio.run() takes control of the event loop startup, our
                # first opportunity to change signal handling behavior will be in the
                # main() function.
                loop.add_signal_handler(sig, handler, sig)
            try:
                while True:
                    print('<Your app is running>')
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                for i in range(3):
                    print('<Your app is shutting down...>')
                    await asyncio.sleep(1)


        def handler(sig):
            loop = asyncio.get_running_loop()
            # Inside the signal handler, we can’t stop the loop as in previous
            # examples, because we’ll get warnings about how the loop was stopped
            # before the task created for main() was completed. Instead, we can
            # initiate task cancellation here, which will ultimately result in the
            # main() task exiting; when that happens, the cleanup handling inside
            # asyncio.run() will take over.
            for task in asyncio.all_tasks(loop=loop):
                task.cancel()
            print(f'Got signal: {sig!s}, shutting down.')
            loop.remove_signal_handler(SIGTERM)
            loop.add_signal_handler(SIGINT, lambda: None)


        if __name__ == '__main__':
            asyncio.run(main())

   To summarize, services would have to:
   #. refactor code to use async facade of Openstack libraries
   #. refactor code to replace or wrap third parties libraries in async mode
   #. implement signal handling to cancel tasks properly and control the life cycle of the event loop

#. Migrate unit tests. As said previously we want to
   avoid regression, so the latter we migrate unit tests the better.

#. releasing the refactors. As Asyncio and Eventlet are now able to live in
   the same process, subtopics could be addressed incrementally. We would
   suggest to try addressing a subtopic in its entirety to simplify progress
   tracking, however, if not possible, it would be feasible to release
   partially migrated sub modules.

#. if new bugs are opened during the migration, and if these bugs are related
   to Eventlet and/or to possible race conditions triggered by using Eventlet,
   then, we would suggest refactoring the impacted code to directly transition
   it to Asyncio and hence avoid wasting time by fixing something that will be
   removed soon.

At first glance libraries migration looks easy ones.

Pro and Cons of the Proposed Solution
=====================================

Moving to asyncio and dropping Eventlet would allow us to move from an
implicit async model to an explicit async model.

Indeed as asyncio is part of the stdlib it apply to itself one of the
main mantra of the Python philosophy, explicit is better than implicit.
Because... implicit comes with hidden complexity. Simplicity is better than
complexity. Obvious. Ockham wouldn't disagree.

We can't count the number of bug opened in the past and even today and who
related to implicit nature of Eventlet. Also we can't ignore the time the
community gained in the past by using Eventlet. By using Eventlet the
community avoided to have to rewrite every piece of code to implement async.
However, that was a time where the gap between CPython and Eventlet was not to
large.

Making effort doing this transition will be paid by allowing us to better
manage and understand our control flow. Making effort doing this transition
will be paid by simplifying debug session if not even reducing the number
of bug related to the networking programming model and to async.

Running this goal would require lot of efforts rewriting everything but
efforts who will be rewarded during the next Openstack decades.

To summarize, this goal, will reward us with major gains:
* better maintainability by moving to an explicit asynchronous model;
* better stability by removing implicit usages of greenthreads and so by also removing lot of potential race conditions;
* better performances by avoiding intensive resources usages related to greenthreads (useless context switching, virtual memory consumption, etc);

Conclusion
==========

A community goal does not shape a new and personal vision of Openstack.
A Community goal collects this vision from the scattered hopes and intentions
of our community's past.

The replacement of Eventlet by Asyncio and the emergence of a new network
programming model in Openstack is the logical continuation of our years of
dedicated work and of the evolution of our main technological pillar, CPython.

The proposed solution is a sustainable solution! Replacing Eventlet by another
third party library with low resources and based on the same monkey patch
model, like by example gevent, would lead us to the same problem sooner than
we think.

Using Asyncio would benefit to everybody. Us and our customers.
Everybody will gain in maintainability, stability, and the last but not the
least, in performances. If performances increase and if resource consumption
decrease it would be translated in cost saving for our customers.

We live at an era where resources are scarce and where we should save them.
Green IT is not only a concept or a fashion, it is an act. An act that start
in changes we made in our daily basis. This is the first step.

Open source is the future of IT. Openstack is one of the undispted leaders of
the open source world. Openstack must lead by example. Openstack must be seen
as reference. Using the right features at the right places will made Openstack
that reference.

Even if Eventlet is fully retired and even if that goal is done, that's not
an end in itself. Indeed, through this goal we would had seen the emergence of
a new network programming model. An architecture model based on asynchronous
capabilities. An optimized architecture model provided by Linux interface and
CPython and specifically designed for our needs.

We should not repeat the same error again. `Eventlet was chosen to unify
architecture of Openstack services <https://wiki.openstack.org/wiki/Obsolete:UnifiedServiceArchitecture>`_.
But the time past and again architectures have diverged.
We should not Maintains different architectures for doing the same thing.
Adopting this new model in all our deliverables would be a logical
continuation for our community. An unified service architecture avoiding an
abundance of integration and adaptation issues. We should see well beyond the
results of this proposal.

Great success are shared success that benefits to everyone!

Champion
========

Hervé Beraud <hberaud@redhat.com> (hberaud)


Gerrit Topic
============

To facilitate tracking, commits related to this goal should use the
gerrit topic::

  modernize-networking-model


Completion Criteria
===================

#. (done) Get an healthy new version of Eventlet;
#. (done) Be able to support Python 3.12 and higher version as an Openstack runtime;
#. (done) Get Asyncio supported by Eventlet and vice versa;
#. Get the Eventlet's Asyncio Hub activated on all deliverables relying on Eventlet;
#. Get the oslo world fully migrated;
#. Get libraries like OpenstackSDK migrated;
#. Get a reference user project elected;
#. Get non actively maintained deliverables retired;
#. Get all other Openstack deliverables relying on Eventlet migrated;
#. Get Eventlet retired from Openstack;
#. Get Eventlet abandoned or bequeath to someone else.

Side note: requirements file could be used to monitor the transition.
Indeed, third parties blocking IO libraries should be removed from
these files over time. It would be a good indicator of the remaining works.
However, we should notice that as some deliverables are not relying on
Eventlet, they can continue to relies on blocking IO third parties libraries
over time.

References
==========

- Using Asyncio in Python - Caleb Hattingh
- 


Previous similar attempts and discussions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- `Replace Eventlet by asyncio, by Victor Stinner <https://review.openstack.org/#/c/153298/>`_
- `Replace eventlet + monkey-patching with threads, by Joshua Harlow <https://review.openstack.org/#/c/156711/>`_
- `Use an asyncio event loop, by Victor Stinner <https://wiki.openstack.org/wiki/Oslo/blueprints/asyncio>`_
- `The oslo.messaging NATS driver <https://lists.openstack.org/archives/list/openstack-discuss@lists.openstack.org/thread/TOZU6ONOSOD6BBHTCBVHWG6HPOOLOW6N/#U4F4I4OURQMIP6PVKARG6UT2JB6XU2PM>`_
- `Specs to add the NATS transport driver to oslo.messaging <https://review.opendev.org/c/openstack/oslo-specs/+/692784>`_


A brief Eventlet history in Openstack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- https://wiki.openstack.org/wiki/Obsolete:UnifiedServiceArchitecture
- https://lists.openstack.org/pipermail/openstack/2012-March/027583.html
- https://code.launchpad.net/~termie/nova/eventlet_merge/+merge/43383
- https://lists.openstack.org/archives/list/openstack-discuss@lists.openstack.org/message/WCCJULVHRZUI7EUVLOUEMCTSPE5YIJGV/

Current State / Anticipated Impact
==================================

* Progress is maintained on the below wiki page:
  https://wiki.openstack.org/wiki/Modernize_Openstack_Networking_Programming_Model
* aihub discussions and pre-specs are currently hosted on the below wiki page:
  https://wiki.openstack.org/wiki/Aiohub-Discussion
* Identification of Eventlet based deliverables that can be easily migrated to
  asyncio is hosted on the below wiki page:
  https://wiki.openstack.org/wiki/Eventlet-Based-Deliverables-Easily-Migrated

Related links:

- https://github.com/eventlet/eventlet/issues/824
- https://github.com/eventlet/eventlet/issues/824#issuecomment-1853128741
- https://github.com/eventlet/eventlet/pull/827
- https://github.com/eventlet/eventlet/pull/831
- https://github.com/eventlet/eventlet/pull/832
- https://github.com/eventlet/eventlet/pull/817
- https://github.com/eventlet/eventlet/pull/847
- https://github.com/eventlet/eventlet/pull/854
- https://github.com/eventlet/eventlet/issues/842
- https://github.com/eventlet/eventlet/issues/861
- https://pypi.org/project/eventlet/0.34.1/
- https://pypi.org/project/eventlet/0.34.2/
- https://review.opendev.org/c/openstack/requirements/+/904147?usp=search
