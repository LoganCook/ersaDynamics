import re
import xml.etree.ElementTree as ET

class FetchXML(object):
    palias = re.compile('^[A-Za-z_][a-zA-Z0-9_]{0,}$')

    @staticmethod
    def create_fetch(distinct=False):
        fetch = ET.Element('fetch')
        fetch.set('mapping', 'logical')
        if distinct:
            fetch.set('distinct', 'true')
        else:
            fetch.set('distinct', 'false')
        return fetch

    @staticmethod
    def create_sub_elm(elm, name, attribs=None):
        """Create a sub-element of an element

        :param element ele: parent element to the element being created
        :param str name: name of the element being created
        :param dict attribs: attributes to be added to the element being created
        """
        entity = ET.SubElement(elm, name)
        if attribs:
            for k, v in attribs.items():
                entity.set(k, v)
        return entity


    @staticmethod
    def create_entity(elm, name):
        attribs = {'name': name}
        return FetchXML.create_sub_elm(elm, 'entity', attribs)


    @staticmethod
    def create_link(elm, source, linked, to, ltype=None, extra=None):
        # linked: primary key of link-entity
        """Create link-entity element

        :param str source: link-entity name
        :param str linked: primary key of link-entity
        :param str to: foreign key of linked key
        :param str ltype: either inner or outer, default is inner
        :param dict extra: any other possible attributes: intersect, visible etc.
        """
        attribs = {'name': source, 'from': linked, 'to': to}
        if ltype:
            attribs['link-type'] = ltype
        if extra:
            attribs.update(extra)
        link = FetchXML.create_sub_elm(elm, 'link-entity', attribs)
        return link

    @staticmethod
    def create_alias(elm, source, target):
        """Create alias attribute element in (link-)entity element

        :param str source: source internal field name
        :param str target: name to be used as alias
        """
        # alias: Only characters within the ranges [A-Z], [a-z] or [0-9] or _ are allowed.
        # The first character may only be in the ranges [A-Z], [a-z] or _.
        assert FetchXML.palias.match(target)
        return FetchXML.create_sub_elm(elm, 'attribute', {'name': source, 'alias': target})

    @staticmethod
    def create_condition(elm, target, operator, value=None):
        """Create condition element in filter element

        :param element target: filter element
        :param str operator: name of operator
        :param str value: value of operator, default: None
        """
        attribs = {'attribute': target, 'operator': operator}
        if value:
            attribs['value'] = value
        return FetchXML.create_sub_elm(elm, 'condition', attribs)

    @staticmethod
    def to_string(elm):
        return ET.tostring(elm, 'unicode')

if __name__ == '__main__':
    fetcher = FetchXML
    fetch = fetcher.create_fetch(True)
    print(fetcher.to_string(fetch))
    ET.dump(fetch)
