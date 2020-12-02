# SPDX-License-Identifier: BSD-2-Clause
""" This module provides specification items and an item cache. """

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
import os
import pickle
import string
import stat
from typing import Any, Callable, Dict, Iterable, Iterator, List, NamedTuple, \
    Mapping, Optional, Tuple, Union
import yaml


class ItemGetValueContext(NamedTuple):
    """ Context used to get an item value. """
    item: "Item"
    path: str
    value: Any
    key: str
    index: Any  # should be int, but this triggers a mypy error


ItemMap = Dict[str, "Item"]
ItemGetValue = Callable[[ItemGetValueContext], Any]
ItemGetValueMap = Dict[str, Tuple[ItemGetValue, Any]]


def _is_enabled_op_and(enabled: List[str], enabled_by: Any) -> bool:
    for next_enabled_by in enabled_by:
        if not is_enabled(enabled, next_enabled_by):
            return False
    return True


def _is_enabled_op_not(enabled: List[str], enabled_by: Any) -> bool:
    return not is_enabled(enabled, enabled_by)


def _is_enabled_op_or(enabled: List[str], enabled_by: Any) -> bool:
    for next_enabled_by in enabled_by:
        if is_enabled(enabled, next_enabled_by):
            return True
    return False


_IS_ENABLED_OP = {
    "and": _is_enabled_op_and,
    "not": _is_enabled_op_not,
    "or": _is_enabled_op_or
}


def is_enabled(enabled: List[str], enabled_by: Any) -> bool:
    """ Verifies if the given parameter is enabled by specific enables. """
    if isinstance(enabled_by, bool):
        return enabled_by
    if isinstance(enabled_by, list):
        return _is_enabled_op_or(enabled, enabled_by)
    if isinstance(enabled_by, dict):
        key, value = next(iter(enabled_by.items()))
        return _IS_ENABLED_OP[key](enabled, value)
    return enabled_by in enabled


def _str_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str",
                                   data,
                                   style="|" if "\n" in data else "")


yaml.add_representer(str, _str_representer)


class Link:
    """ A link to an item. """
    def __init__(self, item: "Item", data: Any):
        self._item = item
        self._data = data

    @classmethod
    def create(cls, link: "Link", item: "Item") -> "Link":
        """ Creates a link using an existing link with a new target item. """
        return cls(item, link._data)  # pylint: disable=protected-access

    def __getitem__(self, name: str) -> Any:
        return self._data[name]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    @property
    def item(self) -> "Item":
        """ The item referenced by this link. """
        return self._item

    @property
    def role(self) -> str:
        """ The link role. """
        return self._data["role"]


def _get_value(ctx: ItemGetValueContext) -> Any:
    value = ctx.value[ctx.key]
    if ctx.index >= 0:
        return value[ctx.index]
    return value


def normalize_key_path(key_path: str, prefix: str = "") -> str:
    """ Normalizes the key path with an optional prefix path. """
    if not os.path.isabs(key_path):
        key_path = os.path.join(prefix, key_path)
    return os.path.normpath(key_path)


class Item:
    """ Objects of this class represent a specification item. """

    # pylint: disable=too-many-public-methods
    def __init__(self, item_cache: "ItemCache", uid: str, data: Any):
        self._cache = item_cache
        self._uid = uid
        self._data = data
        self._links_to_parents = []  # type: List[Link]
        self._links_to_children = []  # type: List[Link]

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Item):
            return NotImplemented
        return self._uid == other._uid  # pylint: disable=protected-access

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Item):
            return NotImplemented
        return self._uid < other._uid  # pylint: disable=protected-access

    def __hash__(self) -> int:
        return hash(self._uid)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    @property
    def cache(self) -> "ItemCache":
        """ Returns the cache of the items. """
        return self._cache

    def get(self, key: str, default: Any) -> Any:
        """
        Gets the attribute value if the attribute exists, otherwise the
        specified default value is returned.
        """
        return self._data.get(key, default)

    def get_by_normalized_key_path(self, normalized_key_path: str,
                                   get_value_map: ItemGetValueMap) -> Any:
        """
        Gets the attribute value corresponding to the normalized key path.
        """
        path = "/"
        value = self._data
        for key in normalized_key_path.strip("/").split("/"):
            parts = key.split("[")
            try:
                index = int(parts[1].split("]")[0])
            except IndexError:
                index = -1
            ctx = ItemGetValueContext(self, path, value, parts[0], index)
            get_value, get_value_map = get_value_map.get(
                parts[0], (_get_value, {}))
            value = get_value(ctx)
            path = os.path.join(path, key)
        return value

    def get_by_key_path(self, key_path: str, prefix: str = "") -> Any:
        """ Gets the attribute value corresponding to the key path. """
        return self.get_by_normalized_key_path(
            normalize_key_path(key_path, prefix), {})

    @property
    def uid(self) -> str:
        """ Returns the UID of the item. """
        return self._uid

    @property
    def spec(self) -> str:
        """ Returns the UID of the item with an URL-like format. """
        return f"spec:{self._uid}"

    def to_abs_uid(self, abs_or_rel_uid: str) -> str:
        """
        Returns the absolute UID of an absolute UID or an UID relative to this
        item.
        """
        if abs_or_rel_uid == ".":
            return self._uid
        if os.path.isabs(abs_or_rel_uid):
            return abs_or_rel_uid
        return os.path.normpath(
            os.path.join(os.path.dirname(self.uid), abs_or_rel_uid))

    def map(self, abs_or_rel_uid: str) -> "Item":
        """
        Maps the absolute UID or the UID relative to this item to the
        corresponding item.
        """
        return self._cache[self.to_abs_uid(abs_or_rel_uid)]

    def links_to_parents(self) -> Iterator[Link]:
        """ Yields the links to the parents of this items. """
        yield from self._links_to_parents

    def parents(
            self,
            role: Optional[Union[str,
                                 Iterable[str]]] = None) -> Iterator["Item"]:
        """ Yields the parents of this items. """
        if role is None:
            for link in self._links_to_parents:
                yield link.item
        elif isinstance(role, str):
            for link in self._links_to_parents:
                if link.role == role:
                    yield link.item
        else:
            for link in self._links_to_parents:
                if link.role in role:
                    yield link.item

    def parent(self,
               role: Optional[Union[str, Iterable[str]]] = None,
               index: Optional[int] = 0) -> "Item":
        """ Returns the parent with the specified role and index. """
        for item_index, item in enumerate(self.parents(role)):
            if item_index == index:
                return item
        raise IndexError

    def links_to_children(self) -> Iterator[Link]:
        """ Yields the links to the children of this items. """
        yield from self._links_to_children

    def children(
            self,
            role: Optional[Union[str,
                                 Iterable[str]]] = None) -> Iterator["Item"]:
        """ Yields the children of this items. """
        if role is None:
            for link in self._links_to_children:
                yield link.item
        elif isinstance(role, str):
            for link in self._links_to_children:
                if link.role == role:
                    yield link.item
        else:
            for link in self._links_to_children:
                if link.role in role:
                    yield link.item

    def child(self,
              role: Optional[Union[str, Iterable[str]]] = None,
              index: Optional[int] = 0) -> "Item":
        """ Returns the child with the specified role and index. """
        for item_index, item in enumerate(self.children(role)):
            if item_index == index:
                return item
        raise IndexError

    def init_parents(self, item_cache: "ItemCache") -> None:
        """ Initializes the list of links to parents of this items. """
        for data in self._data["links"]:
            try:
                link = Link(item_cache[self.to_abs_uid(data["uid"])], data)
                self._links_to_parents.append(link)
            except KeyError as err:
                msg = (f"item '{self.uid}' links "
                       f"to non-existing item '{data['uid']}'")
                raise KeyError(msg) from err

    def init_children(self) -> None:
        """ Initializes the list of links to children of this items. """
        for link in self.links_to_parents():
            link.item.add_link_to_child(Link.create(link, self))

    def add_link_to_child(self, link: Link):
        """ Adds a link to a child item of this items. """
        self._links_to_children.append(link)

    def is_enabled(self, enabled: List[str]):
        """ Returns true if the item is enabled by the specified enables. """
        return is_enabled(enabled, self["enabled-by"])

    @property
    def data(self) -> Any:
        """ The item data. """
        return self._data

    @property
    def file(self) -> str:
        """ Returns the file of the item. """
        return self._data["_file"]

    @file.setter
    def file(self, value: str):
        """ Sets the file of the item. """
        self._data["_file"] = value

    @property
    def type(self) -> str:
        """ Returns the type of the item. """
        return self._data["_type"]

    def save(self):
        """ Saves the item to the corresponding file. """
        with open(self.file, "w") as dst:
            data = {}
            for key, value in self._data.items():
                if not key.startswith("_"):
                    data[key] = value
            dst.write(
                yaml.dump(data, default_flow_style=False, allow_unicode=True))

    def load(self):
        """ Loads the item from the corresponding file. """
        filename = self.file
        with open(filename, "r") as src:
            self._data = yaml.safe_load(src.read())
            self._data["_file"] = filename


class ItemTemplate(string.Template):
    """ String template for item mapper identifiers. """
    idpattern = "[a-zA-Z0-9._/-]+(:[][a-zA-Z0-9._/-]+)?(|[a-zA-Z0-9_]+)*"


class ItemMapper(Mapping[str, object]):
    """ Maps identifiers to items and attribute values. """
    def __init__(self, item: Item, recursive: bool = False):
        self._item = item
        self._recursive = recursive
        self._prefix = [""]
        self._get_value_map = {}  # type: Dict[str, ItemGetValueMap]

    @property
    def item(self) -> Item:
        """ The item of the mapper. """
        return self._item

    @item.setter
    def item(self, item: Item) -> None:
        """ Sets the item of the mapper. """
        self._item = item

    def add_get_value(self, type_path_key: str,
                      get_value: ItemGetValue) -> None:
        """
        Adds a get value for the specified type and key path.
        """
        type_name, path_key = type_path_key.split(":")
        keys = path_key.strip("/").split("/")
        get_value_map = self._get_value_map.setdefault(type_name, {})
        for key in keys[:-1]:
            _, get_value_map = get_value_map.setdefault(key, (_get_value, {}))
        get_value_map[keys[-1]] = (get_value, {})

    def push_prefix(self, prefix: str) -> None:
        """ Pushes a key path prefix. """
        self._prefix.append(prefix)

    def pop_prefix(self) -> None:
        """ Pops a key path prefix. """
        self._prefix.pop()

    @contextmanager
    def prefix(self, prefix: str) -> Iterator[None]:
        """ Opens a key path prefix context. """
        self.push_prefix(prefix)
        yield
        self.pop_prefix()

    def get_value_map(self, item: Item) -> ItemGetValueMap:
        """ Returns the get value map for the item. """
        return self._get_value_map.get(item.type, {})

    def map(self, identifier: str) -> Tuple[Item, str, Any]:
        """
        Maps an identifier to the corresponding item and attribute value.
        """
        uid_key_path, *pipes = identifier.split("|")
        colon = uid_key_path.find(":")
        if colon >= 0:
            uid, key_path = uid_key_path[:colon], uid_key_path[colon + 1:]
        else:
            uid, key_path = uid_key_path, "/_uid"
        if uid == ".":
            item = self._item
            prefix = "/".join(self._prefix)
        else:
            item = self._item.map(uid)
            prefix = ""
        key_path = normalize_key_path(key_path, prefix)
        value = item.get_by_normalized_key_path(key_path,
                                                self.get_value_map(item))
        for func in pipes:
            value = getattr(self, func)(value)
        return item, key_path, value

    @contextmanager
    def _item_and_prefix(self, item: Item, prefix: str) -> Iterator[None]:
        item_2 = self._item
        prefix_2 = self._prefix
        self._item = item
        self._prefix = [prefix]
        yield
        self._item = item_2
        self._prefix = prefix_2

    def __getitem__(self, identifier):
        item, key_path, value = self.map(identifier)
        if self._recursive:
            with self._item_and_prefix(item, os.path.dirname(key_path)):
                return self.substitute(value)
        return value

    def __iter__(self):
        raise StopIteration

    def __len__(self):
        raise AttributeError

    def substitute(self, text: Optional[str]) -> str:
        """ Performs a variable substitution using the item mapper. """
        if not text:
            return ""
        return ItemTemplate(text).substitute(self)

    def substitute_with_prefix(self, text: Optional[str], prefix: str) -> str:
        """
        Performs a variable substitution using the item mapper with a prefix.
        """
        if not text:
            return ""
        with self.prefix(prefix):
            return ItemTemplate(text).substitute(self)


class _SpecType(NamedTuple):
    key: str
    refinements: Dict[str, Any]


def _gather_spec_refinements(item: Item) -> Optional[_SpecType]:
    new_type = None  # type: Optional[_SpecType]
    for link in item.links_to_children():
        if link.role == "spec-refinement":
            key = link["spec-key"]
            if new_type is None:
                new_type = _SpecType(key, {})
            assert new_type.key == key
            new_type.refinements[
                link["spec-value"]] = _gather_spec_refinements(link.item)
    return new_type


def _load_item(path: str, uid: str) -> Any:
    with open(path, "r") as src:
        try:
            data = yaml.safe_load(src.read())
        except yaml.YAMLError as err:
            msg = ("YAML error while loading specification item file "
                   f"'{path}': {str(err)}")
            raise IOError(msg) from err
        data["_file"] = os.path.abspath(path)
        data["_uid"] = uid
    return data


class ItemCache:
    """ This class provides a cache of specification items. """
    def __init__(self, config: Any):
        self._items = {}  # type: ItemMap
        self._top_level = {}  # type: ItemMap
        self._updates = 0
        self._load_items(config)
        spec_root = config["spec-type-root-uid"]
        if spec_root:
            self._root_type = _gather_spec_refinements(self[spec_root])
        else:
            self._root_type = None
        for item in self._items.values():
            self._set_type(item)

    def __getitem__(self, uid: str) -> Item:
        return self._items[uid]

    @property
    def updates(self) -> bool:
        """
        Returns true if the item cache updates occurred due to new, modified,
        or removed files.
        """
        return self._updates > 0

    @property
    def all(self) -> ItemMap:
        """ Returns the map of all specification items. """
        return self._items

    @property
    def top_level(self) -> ItemMap:
        """ Returns the map of top-level specification items. """
        return self._top_level

    def add_volatile_item(self, path: str, uid: str) -> Item:
        """
        Adds an item stored in the specified file to the cache and returns it.

        The item is not added to the persistent cache storage.
        """
        data = _load_item(path, uid)
        item = self._add_item(uid, data)
        item.init_parents(self)
        item.init_children()
        self._set_type(item)
        return item

    def _add_item(self, uid: str, data: Any) -> Item:
        item = Item(self, uid, data)
        self._items[uid] = item
        if not item["links"]:
            self._top_level[uid] = item
        return item

    def _load_items_in_dir(self, base: str, path: str, cache_file: str,
                           update_cache: bool) -> None:
        data_by_uid = {}  # type: Dict[str, Any]
        if update_cache:
            self._updates += 1
            for name in os.listdir(path):
                path2 = os.path.join(path, name)
                if name.endswith(".yml") and not name.startswith("."):
                    uid = "/" + os.path.relpath(path2, base).replace(
                        ".yml", "")
                    data_by_uid[uid] = _load_item(path2, uid)
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, "wb") as out:
                pickle.dump(data_by_uid, out)
        else:
            with open(cache_file, "rb") as pickle_src:
                data_by_uid = pickle.load(pickle_src)
        for uid, data in iter(data_by_uid.items()):
            self._add_item(uid, data)

    def _load_items_recursive(self, base: str, path: str,
                              cache_dir: str) -> None:
        mid = os.path.abspath(path)
        mid = mid.replace(os.path.commonpath([cache_dir, mid]), "").strip("/")
        cache_file = os.path.join(cache_dir, mid, "spec.pickle")
        try:
            mtime = os.path.getmtime(cache_file)
            update_cache = False
        except FileNotFoundError:
            update_cache = True
        else:
            update_cache = mtime <= os.path.getmtime(path)
        for name in os.listdir(path):
            path2 = os.path.join(path, name)
            if name.endswith(".yml") and not name.startswith("."):
                if not update_cache:
                    update_cache = mtime <= os.path.getmtime(path2)
            else:
                if stat.S_ISDIR(os.lstat(path2).st_mode):
                    self._load_items_recursive(base, path2, cache_dir)
        self._load_items_in_dir(base, path, cache_file, update_cache)

    def _init_parents(self) -> None:
        for item in self._items.values():
            item.init_parents(self)

    def _init_children(self) -> None:
        for uid in sorted(self._items):
            self._items[uid].init_children()

    def _load_items(self, config: Any) -> None:
        cache_dir = os.path.abspath(config["cache-directory"])
        for path in config["paths"]:
            self._load_items_recursive(path, path, cache_dir)
        self._init_parents()
        self._init_children()

    def _set_type(self, item: Item) -> None:
        spec_type = self._root_type
        value = item.data
        path = []  # type: List[str]
        while spec_type is not None:
            type_name = value[spec_type.key]
            path.append(type_name)
            spec_type = spec_type.refinements[type_name]
        item["_type"] = "/".join(path)


class EmptyItemCache(ItemCache):
    """ This class provides a empty cache of specification items. """
    def __init__(self):
        super().__init__({
            "cache-directory": ".",
            "paths": [],
            "spec-type-root-uid": None
        })


class EmptyItem(Item):
    """ Objects of this class represent empty items. """
    def __init__(self):
        super().__init__(EmptyItemCache(), "", {})
