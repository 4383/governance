==============================
Remove Eventlet from OpenStack
==============================

OpenStack is built on the top of asynchronous mechanisms.
Many Openstack deliverables use the Eventlet library to obtain asynchronous
those asynchronous mechanismes. Problem, Eventlet lake of active maintainers
and that led that library to a point where Eventlet is broken at each new
CPython versions.

Asyncio based solutions (awaitlet, aiohttp, etc) offers a flexible, perennial,
and modern alteratives to Eventlet. Since the Eventlet Asyncio hub was
released, allowing Eventlet and Asyncio to be ran into the same process, the
community has encouraged the usage of those alternatives and the deprecation
of any existing code still using Eventlet.

Champion
========

- Hervé Beraud <hberaud@redhat.com> (hberaud)

Gerrit Topic
============

To facilitate tracking, commits related to this goal should use the
gerrit topic::

  eventlet-removal

A new sub-task in middle term [1]_ or long term [2]_ stories will be created
to track any related advancement by deliverable.

Completion Criteria
===================

#. Get the oslo deliverables doing networkIO providing Asyncio based drivers
   and backends (oslo.cache, oslo.messaging, oslo.db, etc);
#. Get libraries like OpenStackSDK migrated;
#. Get a reference user project elected;
#. Get non actively maintained deliverables retired;
#. Get all other OpenStack deliverables relying on Eventlet migrated;
#. Get usage of Eventlet in oslo deliverables removed;
#. Get Eventlet retired from OpenStack;
#. Get Eventlet abandoned or bequeath to someone else.

References
==========

<to complete>

Current State / Anticipated Impact
==================================

Progress is maintained on the public tracker links below:
* short term actions (done): [3]_
* middle term actions: [1]_
* long term actions: [2]_

Links
=====

.. [1] https://issues.redhat.com/browse/OSPRH-5960
.. [2] https://issues.redhat.com/browse/OSPRH-5980
.. [3] https://issues.redhat.com/browse/OSPRH-5951
