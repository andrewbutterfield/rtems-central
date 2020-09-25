# SPDX-License-Identifier: BSD-2-Clause
""" This module provides classes for Sphinx content generation. """

# Copyright (C) 2019, 2020 embedded brains GmbH (http://www.embedded-brains.de)
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

from contextlib import contextmanager
from typing import Any, Iterable, Iterator, List, Optional, Union

from rtemsspec.content import Content, make_lines, to_camel_case
from rtemsspec.items import Item, ItemGetValueContext, ItemMapper

GenericContent = Union[str, List[str], "Content"]
GenericContentIterable = Union[Iterable[str], Iterable[List[str]],
                               Iterable[GenericContent]]

_HEADER_LEVELS = ["#", "*", "=", "-", "^", "\""]


def get_reference(label: str, name: Optional[str] = None) -> str:
    """ Returns the reference to the specified label. """
    if name:
        return f":ref:`{name} <{label}>`"
    return f":ref:`{label}`"


def get_label(name: str) -> str:
    """ Returns the label for the specified name. """
    return to_camel_case(name.strip())


class SphinxContent(Content):
    """ This class builds Sphinx content. """
    def __init__(self, section_level: int = 2):
        super().__init__("CC-BY-SA-4.0", True)
        self._tab = "    "
        self._section_level = section_level
        self.section_label_prefix = "Section"

    def add_label(self, label: str) -> None:
        """ Adds a label. """
        self.add(".. _" + label.strip() + ":")

    def add_header(self, name, level=2) -> None:
        """ Adds a header. """
        name = name.strip()
        self.add([name, _HEADER_LEVELS[level] * len(name)])

    def add_header_with_label(self,
                              name: str,
                              level: int = 2,
                              label_prefix: Optional[str] = None) -> str:
        """ Adds a header with label. """
        if label_prefix is None:
            label_prefix = self.section_label_prefix
        label = label_prefix + get_label(name)
        self.add_label(label)
        self.add_header(name, level)
        return label

    def add_index_entries(self, entries) -> None:
        """ Adds a list of index entries the content. """
        self.add([".. index:: " + entry for entry in make_lines(entries)])

    def add_definition_item(self,
                            name: GenericContent,
                            definition: GenericContent,
                            wrap: bool = False) -> None:
        """ Adds a definition item the content. """
        @contextmanager
        def _definition_item_context(content: Content) -> Iterator[None]:
            content.append(name)
            content.push_indent()
            yield
            content.pop_indent()

        if wrap:
            self.wrap(definition, context=_definition_item_context)
        else:
            self.add(definition, context=_definition_item_context)

    @contextmanager
    def definition_item(self, name: GenericContent) -> Iterator[None]:
        """ Opens a definition item context. """
        self.wrap(name)
        self.push_indent()
        yield
        self.pop_indent()

    def open_directive(self,
                       name: str,
                       value: Optional[str] = None,
                       options: Optional[List[str]] = None) -> None:
        """ Opens a directive. """
        value = " " + value if value else ""
        self.add(f".. {name.strip()}::{value}")
        self.push_indent()
        self.add(options)
        self.gap = True

    def close_directive(self) -> None:
        """ Closes a directive. """
        self.pop_indent()

    @contextmanager
    def directive(self,
                  name: str,
                  value: Optional[str] = None,
                  options: Optional[List[str]] = None):
        """ Opens a directive context. """
        self.open_directive(name, value, options)
        yield
        self.close_directive()

    def open_section(self,
                     name: str,
                     label_prefix: Optional[str] = None) -> str:
        """ Opens a section. """
        label = self.add_header_with_label(name, self._section_level,
                                           label_prefix)
        self._section_level += 1
        return label

    def close_section(self) -> None:
        """ Closes a section. """
        self._section_level -= 1

    @contextmanager
    def section(self,
                name: str,
                label_prefix: Optional[str] = None) -> Iterator[str]:
        """ Opens a section context. """
        yield self.open_section(name, label_prefix)
        self.close_section()

    def add_list_item(self, content: GenericContent) -> None:
        """ Adds a list item. """
        self.wrap(content, initial_indent="* ", subsequent_indent="  ")

    def add_list(self,
                 items: GenericContentIterable,
                 prologue: Optional[GenericContent] = None,
                 epilogue: Optional[GenericContent] = None,
                 add_blank_line: bool = False) -> None:
        """ Adds a list with introduction. """
        if items:
            self.wrap(prologue)
            for item in items:
                self.add_list_item(item)
            if add_blank_line:
                self.add_blank_line()
            self.wrap(epilogue)

    def open_list_item(self, content: GenericContent) -> None:
        """ Opens a list item. """
        self.add(["* "])
        self.push_indent("  ")
        self.gap = True
        self.paste(content)

    def close_list_item(self) -> None:
        """ Closes a list item. """
        self.pop_indent()
        self.gap = True

    @contextmanager
    def list_item(self, content: GenericContent) -> Iterator[None]:
        """ Opens a list item context. """
        self.open_list_item(content)
        yield
        self.close_list_item()

    def add_licence_and_copyrights(self) -> None:
        """
        Adds a licence and copyright block according to the registered licenses
        and copyrights.
        """
        statements = self._copyrights.get_statements()
        if statements:
            self.prepend("")
            self.prepend([f".. {stm}" for stm in statements])
        self.prepend([f".. SPDX-License-Identifier: {self._license}", ""])

    def open_comment_block(self) -> None:
        """ Opens a comment block. """
        self.push_indent(".. ", "..")


def _get_ref_term(ctx: ItemGetValueContext) -> Any:
    return f":term:`{ctx.value[ctx.key]}`"


def _get_ref_term_plural(ctx: ItemGetValueContext) -> Any:
    try:
        return f":term:`{ctx.value[ctx.key]} <{ctx.value['term']}>`"
    except KeyError:
        return f":term:`{ctx.value['term']}s <{ctx.value['term']}>`"


def _get_appl_config_option(ctx: ItemGetValueContext) -> Any:
    return f":ref:`{ctx.value[ctx.key]}`"


def _get_value_sphinx_macro(ctx: ItemGetValueContext) -> Any:
    return f":c:macro:`{ctx.value[ctx.key]}`"


def _get_value_sphinx_function(ctx: ItemGetValueContext) -> Any:
    return f":c:func:`{ctx.value[ctx.key]}`"


def _get_value_sphinx_type(ctx: ItemGetValueContext) -> Any:
    return f":c:type:`{ctx.value[ctx.key]}`"


def _get_value_sphinx_url(ctx: ItemGetValueContext) -> Any:
    return f"`{ctx.value[ctx.key]} <{ctx.item['reference']}>`_"


def _get_value_sphinx_unspecified_define(ctx: ItemGetValueContext) -> Any:
    if ctx.item["reference"]:
        return _get_value_sphinx_url(ctx)
    return _get_value_sphinx_macro(ctx)


def _get_value_sphinx_unspecified_type(ctx: ItemGetValueContext) -> Any:
    if ctx.item["reference"]:
        return _get_value_sphinx_url(ctx)
    return _get_value_sphinx_type(ctx)


class SphinxMapper(ItemMapper):
    """ Sphinx item mapper. """
    def __init__(self, item: Item):
        super().__init__(item)
        self.add_get_value("glossary/term:/term", _get_ref_term)
        self.add_get_value("glossary/term:/plural", _get_ref_term_plural)
        self.add_get_value("interface/appl-config-option/feature-enable:/name",
                           _get_appl_config_option)
        self.add_get_value("interface/appl-config-option/feature:/name",
                           _get_appl_config_option)
        self.add_get_value("interface/appl-config-option/initializer:/name",
                           _get_appl_config_option)
        self.add_get_value("interface/appl-config-option/integer:/name",
                           _get_appl_config_option)
        self.add_get_value("interface/define:/name", _get_value_sphinx_macro)
        self.add_get_value("interface/enum:/name", _get_value_sphinx_type)
        self.add_get_value("interface/function:/name",
                           _get_value_sphinx_function)
        self.add_get_value("interface/macro:/name", _get_value_sphinx_function)
        self.add_get_value("interface/struct:/name", _get_value_sphinx_type)
        self.add_get_value("interface/typedef:/name", _get_value_sphinx_type)
        self.add_get_value("interface/union:/name", _get_value_sphinx_type)
        self.add_get_value("interface/unspecified-define:/name",
                           _get_value_sphinx_unspecified_define)
        self.add_get_value("interface/unspecified-function:/name",
                           _get_value_sphinx_function)
        self.add_get_value("interface/unspecified-type:/name",
                           _get_value_sphinx_unspecified_type)
