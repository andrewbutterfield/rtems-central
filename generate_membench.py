#!/usr/bin/env python
# SPDX-License-Identifier: BSD-2-Clause
""" Generates memory benchmarks. """

# Copyright (C) 2021 embedded brains GmbH (http://www.embedded-brains.de)
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import argparse
import logging
import os
import sys
import textwrap
from typing import NamedTuple, List, Optional

from rtemsspec.items import ItemCache
from rtemsspec.membench import generate
from rtemsspec.sphinxcontent import SphinxContent, SphinxMapper
from rtemsspec.util import load_config


class _Test(NamedTuple):
    path: str
    name: str
    links: List[str]
    topic: str
    desc: Optional[str]
    init: str
    config: str


_CONFIG_DEFAULT = """#define TASK_ATTRIBUTES RTEMS_DEFAULT_ATTRIBUTES

#define TASK_STORAGE_SIZE \\
  RTEMS_TASK_STORAGE_SIZE( \\
    RTEMS_MINIMUM_STACK_SIZE, \\
    TASK_ATTRIBUTES \
  )

#define CONFIGURE_APPLICATION_DOES_NOT_NEED_CLOCK_DRIVER

#define CONFIGURE_MAXIMUM_FILE_DESCRIPTORS 0

#define CONFIGURE_DISABLE_NEWLIB_REENTRANCY

#define CONFIGURE_APPLICATION_DISABLE_FILESYSTEM

#define CONFIGURE_MAXIMUM_TASKS 1

#define CONFIGURE_RTEMS_INIT_TASKS_TABLE

#define CONFIGURE_INIT_TASK_ATTRIBUTES TASK_ATTRIBUTES

#define CONFIGURE_INIT_TASK_INITIAL_MODES RTEMS_DEFAULT_MODES

#define CONFIGURE_INIT_TASK_CONSTRUCT_STORAGE_SIZE TASK_STORAGE_SIZE"""

_TEXT = ("The system shall provide a benchmark program to show the static "
         "memory usage of")

_TEST = "This static memory usage benchmark program facilitates"

_LINKS_BASIC = ["../../req/mem-basic"]

_TESTS = [
    _Test(
        "rtems",
        "basic",
        ["/req/mem-benchmark"],
        "a basic application configuration",
        """This resource benchmark is configured for exactly one processor,
no clock driver, no Newlib reentrancy support, and no file system.""",
        """/* Nothing to do */""", _CONFIG_DEFAULT),
    _Test(
        "rtems",
        "smp-1",
        ["mem-basic"],
        """a basic application configuration with
${/acfg/if/max-processors:/name} defined to one using the SMP EDF scheduler
(${/acfg/if/scheduler-edf-smp:/name})""",
        None,
        """/* Nothing to do */""",
        """#define CONFIGURE_MAXIMUM_PROCESSORS 1

#if defined(RTEMS_SMP)
#define CONFIGURE_SCHEDULER_EDF_SMP
#endif

""" + _CONFIG_DEFAULT),
    _Test(
        "rtems",
        "smp-global-2",
        ["mem-smp-1"],
        """a basic application configuration with
${/acfg/if/max-processors:/name} defined to two using the global SMP EDF
scheduler (${/acfg/if/scheduler-edf-smp:/name})""",
        None,
        """/* Nothing to do */""",
        """#define CONFIGURE_MAXIMUM_PROCESSORS 2

#if defined(RTEMS_SMP)
#define CONFIGURE_SCHEDULER_EDF_SMP
#endif

""" + _CONFIG_DEFAULT),
    _Test(
        "rtems",
        "smp-global-4",
        ["mem-smp-1"],
        """a basic application configuration with
${/acfg/if/max-processors:/name} defined to four using the global SMP EDF
scheduler (${/acfg/if/scheduler-edf-smp:/name})""",
        None,
        """/* Nothing to do */""",
        """#define CONFIGURE_MAXIMUM_PROCESSORS 4

#if defined(RTEMS_SMP)
#define CONFIGURE_SCHEDULER_EDF_SMP
#endif

""" + _CONFIG_DEFAULT),
    _Test(
        "rtems",
        "smp-part-2",
        ["mem-smp-1"],
        """a basic application configuration with
${/acfg/if/max-processors:/name} defined to two using one SMP EDF scheduler
for each configured processor (${/acfg/if/scheduler-edf-smp:/name})""",
        None,
        """/* Nothing to do */""",
        """#define CONFIGURE_MAXIMUM_PROCESSORS 2

#if defined(RTEMS_SMP)
#define CONFIGURE_SCHEDULER_EDF_SMP

#include <rtems/scheduler.h>

RTEMS_SCHEDULER_EDF_SMP( a );

RTEMS_SCHEDULER_EDF_SMP( b );

#define NAME( x ) rtems_build_name( x, ' ', ' ', ' ' )

#define CONFIGURE_SCHEDULER_TABLE_ENTRIES \\
  RTEMS_SCHEDULER_TABLE_EDF_SMP( a, NAME( 'A' ) ), \\
  RTEMS_SCHEDULER_TABLE_EDF_SMP( b, NAME( 'B' ) )

#define CONFIGURE_SCHEDULER_ASSIGNMENTS \\
  RTEMS_SCHEDULER_ASSIGN( 0, RTEMS_SCHEDULER_ASSIGN_PROCESSOR_MANDATORY ), \\
  RTEMS_SCHEDULER_ASSIGN( 1, RTEMS_SCHEDULER_ASSIGN_PROCESSOR_MANDATORY )
#endif

""" + _CONFIG_DEFAULT),
    _Test(
        "rtems",
        "smp-part-4",
        ["mem-smp-1"],
        """a basic application configuration with
${/acfg/if/max-processors:/name} defined to four using one SMP EDF scheduler
for each configured processor (${/acfg/if/scheduler-edf-smp:/name})""",
        None,
        """/* Nothing to do */""",
        """#define CONFIGURE_MAXIMUM_PROCESSORS 4

#if defined(RTEMS_SMP)
#define CONFIGURE_SCHEDULER_EDF_SMP

#include <rtems/scheduler.h>

RTEMS_SCHEDULER_EDF_SMP( a );

RTEMS_SCHEDULER_EDF_SMP( b );

RTEMS_SCHEDULER_EDF_SMP( c );

RTEMS_SCHEDULER_EDF_SMP( d );

#define NAME( x ) rtems_build_name( x, ' ', ' ', ' ' )

#define CONFIGURE_SCHEDULER_TABLE_ENTRIES \\
  RTEMS_SCHEDULER_TABLE_EDF_SMP( a, NAME( 'A' ) ), \\
  RTEMS_SCHEDULER_TABLE_EDF_SMP( b, NAME( 'B' ) ), \\
  RTEMS_SCHEDULER_TABLE_EDF_SMP( c, NAME( 'C' ) ), \\
  RTEMS_SCHEDULER_TABLE_EDF_SMP( d, NAME( 'D' ) )

#define CONFIGURE_SCHEDULER_ASSIGNMENTS \\
  RTEMS_SCHEDULER_ASSIGN( 0, RTEMS_SCHEDULER_ASSIGN_PROCESSOR_MANDATORY ), \\
  RTEMS_SCHEDULER_ASSIGN( 1, RTEMS_SCHEDULER_ASSIGN_PROCESSOR_MANDATORY ), \\
  RTEMS_SCHEDULER_ASSIGN( 2, RTEMS_SCHEDULER_ASSIGN_PROCESSOR_MANDATORY ), \\
  RTEMS_SCHEDULER_ASSIGN( 3, RTEMS_SCHEDULER_ASSIGN_PROCESSOR_MANDATORY )
#endif

""" + _CONFIG_DEFAULT),
    _Test(
        "dev/clock",
        "driver",
        ["/rtems/req/mem-basic"],
        """"a basic application configuration with the clock driver enabled
(${/acfg/if/appl-needs-clock-driver:/name})""",
        None,
        """/* Nothing to do */""",
        _CONFIG_DEFAULT.replace(
            "CONFIGURE_APPLICATION_DOES_NOT_NEED_CLOCK_DRIVER",
            "CONFIGURE_APPLICATION_NEEDS_CLOCK_DRIVER")),
    _Test(
        "rtems/barrier",
        "wait-rel",
        _LINKS_BASIC,
        """a basic application configuration with
${/acfg/if/max-barriers:/name} defined to one and calls to
${../if/create:/name}, ${../if/wait:/name}, and ${../if/release:/name}""",
        None,
        """(void) rtems_barrier_create( 0, 0, 0, NULL );
(void) rtems_barrier_wait( 0, 0 );
(void) rtems_barrier_release( 0, NULL );""",
        """#define CONFIGURE_MAXIMUM_BARRIERS 1

""" + _CONFIG_DEFAULT),
    _Test(
        "rtems/barrier",
        "wait-rel-del",
        _LINKS_BASIC,
        """a basic application configuration
with ${/acfg/if/max-barriers:/name} defined to one and calls to
${../if/create:/name}, ${../if/wait:/name}, ${../if/release:/name}, and
${../if/delete:/name}""",
        None,
        """(void) rtems_barrier_create( 0, 0, 0, NULL );
(void) rtems_barrier_wait( 0, 0 );
(void) rtems_barrier_release( 0, NULL );
(void) rtems_barrier_delete( 0 );""",
        """#define CONFIGURE_MAXIMUM_BARRIERS 1

""" + _CONFIG_DEFAULT),
    _Test(
        "rtems/event",
        "snd-rcv",
        _LINKS_BASIC,
        """a basic application configuration with calls to ${../if/send:/name}
and ${../if/receive:/name}""",
        None,
        """(void) rtems_event_send( 0, 0 );
(void) rtems_event_receive( 0, 0, 0, NULL );""",
        _CONFIG_DEFAULT),
    _Test(
        "rtems/fatal",
        "fatal",
        _LINKS_BASIC,
        """a basic application configuration with a call to
${../if/fatal:/name}""",
        None,
        "rtems_fatal( 0, 0 );",
        _CONFIG_DEFAULT),
    _Test(
        "rtems/part",
        "get-ret",
        _LINKS_BASIC,
        """a basic application configuration with
${/acfg/if/max-partitions:/name} defined to one and calls to
${../if/create:/name}, ${../if/get-buffer:/name}, and
${../if/return-buffer:/name}""",
        None,
        """(void) rtems_partition_create( 0, NULL, 0, 0, 0, NULL );
(void) rtems_partition_get_buffer( 0, NULL );
(void) rtems_partition_return_buffer( 0, NULL );""",
        """#define CONFIGURE_MAXIMUM_PARTITIONS 1

""" + _CONFIG_DEFAULT),
    _Test(
        "rtems/part",
        "get-ret-del",
        _LINKS_BASIC,
        """a basic application configuration with
${/acfg/if/max-partitions:/name} defined to one and calls to
${../if/create:/name}, ${../if/get-buffer:/name}, ${../if/return-buffer:/name},
and ${../if/delete:/name}""",
        None,
        """(void) rtems_partition_create( 0, NULL, 0, 0, 0, NULL );
(void) rtems_partition_get_buffer( 0, NULL );
(void) rtems_partition_return_buffer( 0, NULL );
(void) rtems_partition_delete( 0 );""",
        """#define CONFIGURE_MAXIMUM_PARTITIONS 1

""" + _CONFIG_DEFAULT),
    _Test(
        "rtems/ratemon",
        "period",
        _LINKS_BASIC,
        """a basic application configuration with
${/acfg/if/max-periods:/name} defined to one and calls to
${../if/create:/name} and ${../if/period:/name}""",
        None,
        """(void) rtems_rate_monotonic_create( 0, NULL );
(void) rtems_rate_monotonic_period( 0, 0 );""",
        """#define CONFIGURE_MAXIMUM_PERIODS 1

""" + _CONFIG_DEFAULT),
    _Test(
        "rtems/ratemon",
        "period-del",
        _LINKS_BASIC,
        """a basic application configuration with
${/acfg/if/max-periods:/name} defined to one and calls to
${../if/create:/name}, ${../if/period:/name}, and
${../if/delete:/name}""",
        None,
        """(void) rtems_rate_monotonic_create( 0, NULL );
(void) rtems_rate_monotonic_period( 0, 0 );
(void) rtems_rate_monotonic_delete( 0 );""",
        """#define CONFIGURE_MAXIMUM_PERIODS 1

""" + _CONFIG_DEFAULT),
    _Test(
        "rtems/sem",
        "obt-rel",
        _LINKS_BASIC,
        """a basic application configuration with
${/acfg/if/max-semaphores:/name} defined to one and calls to
${../if/create:/name}, ${../if/obtain:/name}, and ${../if/release:/name}""",
        None,
        """(void) rtems_semaphore_create( 0, 0, 0, 0, NULL );
(void) rtems_semaphore_obtain( 0, 0, 0 );
(void) rtems_semaphore_release( 0 );""",
        """#define CONFIGURE_MAXIMUM_SEMAPHORES 1

""" + _CONFIG_DEFAULT),
    _Test(
        "rtems/sem",
        "obt-rel-del",
        _LINKS_BASIC,
        """a basic application configuration with
${/acfg/if/max-semaphores:/name} defined to one and calls to
${../if/create:/name}, ${../if/obtain:/name}, ${../if/release:/name}, and
${../if/delete:/name}""",
        None,
        """(void) rtems_semaphore_create( 0, 0, 0, 0, NULL );
(void) rtems_semaphore_obtain( 0, 0, 0 );
(void) rtems_semaphore_release( 0 );
(void) rtems_semaphore_delete( 0 );""",
        """#define CONFIGURE_MAXIMUM_SEMAPHORES 1

""" + _CONFIG_DEFAULT),
    _Test(
        "rtems/signal",
        "catch-snd",
        _LINKS_BASIC,
        """a basic application configuration with calls to ${../if/catch:/name}
and ${../if/send:/name}""",
        None,
        """(void) rtems_signal_catch( NULL, 0 );
(void) rtems_signal_send( 0, 0 );""",
        _CONFIG_DEFAULT),
    _Test(
        "rtems/task",
        "del",
        _LINKS_BASIC,
        """a basic application configuration with a
call to ${../if/delete:/name}""",
        None,
        """(void) rtems_task_delete( 0 );
""",
        _CONFIG_DEFAULT),
    _Test(
        "rtems/task",
        "exit",
        _LINKS_BASIC,
        """a basic application configuration with a
call to ${../if/exit:/name}""",
        None,
        """rtems_task_exit();
""",
        _CONFIG_DEFAULT),
    _Test(
        "rtems/task",
        "restart",
        _LINKS_BASIC,
        """a basic application configuration with a
call to ${../if/restart:/name}""",
        None,
        """(void) rtems_task_restart( 0, 0 );
""",
        _CONFIG_DEFAULT),
    _Test(
        "rtems/task",
        "sus-res",
        _LINKS_BASIC,
        """a basic application configuration with
calls to ${../if/suspend:/name} and ${../if/resume:/name}""",
        None,
        """(void) rtems_task_suspend( 0 );
(void) rtems_task_resume( 0 );
""",
        _CONFIG_DEFAULT),
]  # yapf: disable


def _indent(lines: str, level: int = 2) -> str:
    space = " " * level
    return lines.replace("\n", f"\n{space}").replace(f"\n{space}\n", "\n\n")


def _text(lines: str, level: int = 2) -> str:
    wrapper = textwrap.TextWrapper()
    wrapper.break_long_words = False
    wrapper.break_on_hyphens = False
    wrapper.width = 79 - level
    return _indent("\n".join(wrapper.wrap(lines)), level)


def _block(lines: Optional[str], level: int = 2) -> str:
    if lines:
        return f"""|
  {_text(lines, level)}"""
    return "null"


def _links(links: List[str]) -> str:
    text = []  # type: List[str]
    for link in links:
        text.append(f"""- role: requirement-refinement
  uid: {link}""")
    return "\n".join(text)


def _generate_files() -> None:
    for test in _TESTS:
        module = os.path.basename(test.path)
        base = f"testsuites/membench/mem-{module}-{test.name}"
        source = f"{base}.c"
        build_spec = f"modules/rtems/spec/build/{base}.yml"
        with open(build_spec, "w") as out:
            out.write(f"""SPDX-License-Identifier: CC-BY-SA-4.0 OR BSD-2-Clause
build-type: test-program
cflags: []
copyrights:
- Copyright (C) 2021 embedded brains GmbH (http://www.embedded-brains.de)
cppflags: []
cxxflags: []
enabled-by: true
features: c cprogram
includes: []
ldflags: []
links: []
source:
- {source}
stlib: []
target: {base}.norun.exe
type: build
use-after: []
use-before: []
""")
        req_spec = f"/{test.path}/req/mem-{test.name}"
        text = _text(f"{_TEXT} {test.topic}.")
        with open(f"spec{req_spec}.yml", "w") as out:
            out.write(f"""SPDX-License-Identifier: CC-BY-SA-4.0 OR BSD-2-Clause
copyrights:
- Copyright (C) 2021 embedded brains GmbH (http://www.embedded-brains.de
enabled-by: true
links:
{_links(test.links)}
non-functional-type: quality
rationale: null
references: []
requirement-type: non-functional
text: |
  {text}
type: requirement
""")
        val_spec = f"spec/{test.path}/val/mem-{test.name}.yml"
        brief = _text(f"{_TEST} {test.topic}.")
        with open(val_spec, "w") as out:
            out.write(f"""SPDX-License-Identifier: CC-BY-SA-4.0 OR BSD-2-Clause
copyrights:
- Copyright (C) 2021 embedded brains GmbH (http://www.embedded-brains.de)
enabled-by: true
links:
- role: validation
  uid: ../req/mem-{test.name}
test-brief: |
  {brief}
test-code: |
  static void Init( rtems_task_argument arg )
  {{
    (void) arg;

    {_indent(test.init, 4)}
  }}

  {_indent(test.config)}

  #define CONFIGURE_INIT

  #include <rtems/confdefs.h>
test-description: {_block(test.desc)}
test-includes:
- rtems.h
test-local-includes: []
test-target: {source}
type: test-suite
""")


def _post_process(path: str) -> None:
    config = load_config("config.yml")
    item_cache = ItemCache(config["spec"])
    root = item_cache["/rtems/req/mem-basic"]
    content = SphinxContent()
    table_pivots = ["/rtems/req/mem-basic", "/rtems/req/mem-smp-1"]
    generate(content, root, SphinxMapper(root), table_pivots, path)
    print(content)


def main() -> None:
    """ Generates memory benchmarks. """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--log-level',
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        type=str.upper,
        default="ERROR",
        help="log level")
    parser.add_argument('--log-file',
                        type=str,
                        default=None,
                        help="log to this file")
    parser.add_argument('--post-process', help="post-process the ELF files")
    args = parser.parse_args(sys.argv[1:])
    logging.basicConfig(filename=args.log_file, level=args.log_level)
    if args.post_process:
        _post_process(args.post_process)
    else:
        _generate_files()


if __name__ == "__main__":
    main()
