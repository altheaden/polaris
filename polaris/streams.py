import importlib.resources as imp_res
from copy import deepcopy

from jinja2 import Template
from lxml import etree


def read(package, streams_filename, tree=None, replacements=None):
    """
    Parse the given streams file

    Parameters
    ----------
    package : Package
        The package name or module object that contains the streams file

    streams_filename : str
        The name of the streams file to read from

    tree : lxml.etree, optional
        An existing set of streams to add to or modify

    replacements : dict, optional
        A dictionary of replacements, in which case ``streams_filename`` is
        assumed to be a Jinja2 template to be rendered with these replacements

    Returns
    -------
    tree : lxml.etree
        A tree of XML data describing MPAS i/o streams with the content from
        the given streams file
    """
    text = imp_res.files(package).joinpath(streams_filename).read_text()
    if replacements is not None:
        template = Template(text)
        text = template.render(**replacements)

    new_tree = etree.fromstring(text)

    tree = update_tree(tree, new_tree)

    return tree


def write(streams, out_filename):
    """write the streams XML data to the file"""

    with open(out_filename, 'w') as stream_file:
        stream_file.write('<streams>\n')

        # Write out all immutable streams first
        for stream in streams.findall('immutable_stream'):
            stream_name = stream.attrib['name']

            stream_file.write('\n')
            stream_file.write(f'<immutable_stream name="{stream_name}"')
            # Process all attributes on the stream
            for attr, val in stream.attrib.items():
                if attr.strip() != 'name':
                    stream_file.write(f'\n                  {attr}="{val}"')

            stream_file.write('/>\n')

        # Write out all immutable streams
        for stream in streams.findall('stream'):
            stream_name = stream.attrib['name']

            stream_file.write('\n')
            stream_file.write(f'<stream name="{stream_name}"')

            # Process all attributes
            for attr, val in stream.attrib.items():
                if attr.strip() != 'name':
                    stream_file.write(f'\n        {attr}="{val}"')

            stream_file.write('>\n\n')

            # Write out all contents of the stream
            for tag in ['stream', 'var_struct', 'var_array', 'var']:
                for child in stream.findall(tag):
                    child_name = child.attrib['name']
                    if tag == 'stream' and child_name == stream_name:
                        # don't include the stream itself
                        continue
                    if 'packages' in child.attrib.keys():
                        package_name = child.attrib['packages']
                        entry = (
                            f'    <{tag} name="{child_name}" '
                            f'packages="{package_name}"/>\n'
                        )
                    else:
                        entry = f'    <{tag} name="{child_name}"/>\n'
                    stream_file.write(entry)

            stream_file.write('</stream>\n')

        stream_file.write('\n')
        stream_file.write('</streams>\n')


def update_defaults(new_child, defaults):
    """
    Update a stream or its children (sub-stream, var, etc.) starting from the
    defaults or add it if it's new.
    """
    if 'name' not in new_child.attrib:
        return

    name = new_child.attrib['name']
    found = False
    for child in defaults:
        if child.attrib['name'] == name:
            found = True
            if child.tag != new_child.tag:
                raise ValueError(
                    f'Trying to update stream "{name}" with '
                    f'inconsistent tags {child.tag} vs. '
                    f'{new_child.tag}.'
                )

            # copy the attributes
            for attr, value in new_child.attrib.items():
                child.attrib[attr] = value

            if len(new_child) > 0:
                # we don't want default grandchildren
                for grandchild in child:
                    child.remove(grandchild)

            # copy or add the grandchildren's contents
            for new_grandchild in new_child:
                update_defaults(new_grandchild, child)

    if not found:
        # add a deep copy of the element
        defaults.append(deepcopy(new_child))


def update_tree(tree, new_tree):
    """
    Parse the given streams file

    Parameters
    ----------
    tree : lxml.etree
        An existing set of streams to add to or modify

    new_tree : lxml.etree
        A new set of streams to add or modify

    Returns
    -------
    tree : lxml.etree
        A tree of XML data describing MPAS i/o streams with the content from
        the given streams file
    """

    if tree is None:
        tree = new_tree
    else:
        streams = next(tree.iter('streams'))
        new_streams = next(new_tree.iter('streams'))

        for new_stream in new_streams:
            _update_element(new_stream, streams)

    return tree


def _update_element(new_child, elements):
    """
    add the new child/grandchildren or add/update attributes if they exist
    """
    if 'name' not in new_child.attrib:
        return

    name = new_child.attrib['name']
    found = False
    for child in elements:
        if child.attrib['name'] == name:
            found = True
            if child.tag != new_child.tag:
                raise ValueError(
                    f'Trying to update stream "{name}" with '
                    f'inconsistent tags {child.tag} vs. '
                    f'{new_child.tag}.'
                )

            # copy the attributes
            for attr, value in new_child.attrib.items():
                child.attrib[attr] = value

            # copy or add the grandchildren's contents
            for new_grandchild in new_child:
                _update_element(new_grandchild, child)

    if not found:
        # add a deep copy of the element
        elements.append(deepcopy(new_child))


def set_default_io_type(tree, io_type='pnetcdf,cdf5'):
    """
    Set io_type attribute for all <stream> and <immutable_stream>
    elements if not already set, except for immutable_stream with name 'mesh'.
    """
    streams = next(tree.iter('streams'))
    all_streams = streams.findall('stream') + streams.findall(
        'immutable_stream'
    )
    for stream in all_streams:
        stream_type = stream.attrib.get('type')
        if 'io_type' not in stream.attrib and 'output' in stream_type:
            stream.attrib['io_type'] = io_type
