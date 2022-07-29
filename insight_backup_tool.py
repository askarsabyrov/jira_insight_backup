#!/usr/bin/env python3
import argparse
import requests
import json
import os
import sys
import re

test_mode=True

parser = argparse.ArgumentParser(description='Backup or restore object schema')
parser.add_argument("-a", "--action", help="backup or restore schema", choices = ['backup', 'restore'] ,required=True)
parser.add_argument("-n", "--schema-keys", help="Schema keys, separated by comma", default="BUSASSETS,GEN,ITASSETS,ITDM,JAG,OMS,PEOPLE,SVC,WP", required=False)
parser.add_argument("-w", "--workspace-id", help="Workspace id", required=True)
parser.add_argument("-d", "--data-dir", help="Data directory", required=True)
parser.add_argument("-u", "--username", help="Username", required=True)
parser.add_argument("-p", "--password", help="Password", required=True)

args = parser.parse_args()
username = args.username
password = args.password
workspace_id = args.workspace_id
schema_keys = args.schema_keys.split(',')
data_dir = args.data_dir
action = args.action


class HTTPApi():
    def __init__(self, username, password, headers=None):
        self.address = f"https://api.atlassian.com/jsm/insight/workspace/{workspace_id}/v1/"
        self.username = username
        self.password = password
        self.headers = headers

    def get(self, path, params=None):
        req = requests.get(f"{self.address}{path}",
                           headers=self.headers,
                           params=params,
                           auth=(self.username, self.password))
        return req

    def post(self, path, data):
        req = requests.post(f"{self.address}{path}",
                             headers=self.headers,
                             auth=(self.username, self.password),
                             json=data)
        if req.status_code not in (200, 201):
            print(f"ERROR: {req.text}")
            sys.exit(1)
        return req

class InsightSchema(HTTPApi):
    def get_schema(self, schema_id):
        path = f"objectschema/{id}"
        return self.get(path).json()

    def get_schema_list(self):
        path = "objectschema/list"
        return self.get(path).json()['values']

    def get_schema_by_key(self, schema_key):
        schemas = self.get_schema_list()
        for schema in schemas:
            if schema['objectSchemaKey'] == schema_key:
                res = schema
                break
        else:
            return {}
        return res

    def get_schema_id(self, schema_key):
        schemas = self.get_schema_list()
        for schema in schemas:
            if schema['objectSchemaKey'] == schema_key:
                res = schema['id']
                break
        return res

    def get_iql(self, request):
        path = f"iql/objects"

    def get_schema_objecttypes(self, schema_id):
        path = f"objectschema/{schema_id}/objecttypes/flat"
        return self.get(path).json()

    def get_objtype_attributes(self, objtype_id):
        path = f"objecttype/{objtype_id}/attributes"
        return self.get(path).json()

    def create_schema(self, data):
        path = "objectschema/create"
        print(f"Creating schema: {data['name']}")
        print(data)
        return self.post(path, data).ok

    def create_objecttype(self, data):
        path = "objecttype/create"
        print(f"Creating object type: {data['name']}")
        print(data)
        api_id = self.post(path, data).json()['id']
        print(f"API ID: {api_id}")
        return api_id

    def create_objecttype_attr(self, object_type_id, data):
        path = f"objecttypeattribute/{object_type_id}"
        print(f"Creating attr: {data['name']}")
        print(data)
        return self.post(path, data).ok

    def allow_other_schemas(self, schema_id):
        path = f"global/config/objectschema/{schema_id}/property"
        data = {"allowOtherObjectSchema": True}
        return self.post(path, data).ok

class Schemas():
    def __init__(self):
        self.schemas = {}

class Schema():
    def __init__(self, schema_file):
        self.id = schema_file['id']
        self.name = schema_file['name']
        self.key = schema_file['objectSchemaKey']
        self.description = schema_file.get('description', '')
        self.api_id = None
        self.object_types = {}

class ObjectType():
    def __init__(self, objtype_file):
        self.id = objtype_file['id']
        self.name = objtype_file['name']
        self.icon_id = objtype_file['icon']['id']
        self.parent_id = objtype_file.get('parentObjectTypeId', None)
        self.api_id = None
        self.attributes = []

class Attribute():
    def __init__(self, attr_file):
        self.id = attr_file['id']
        self.name = attr_file['name']
        self.description = attr_file.get('description', "")
        self.object_type_name = attr_file['objectType']['name']
        self.label = attr_file['label']
        self.type = attr_file['type']
        self.default_type = attr_file.get('defaultType', {})
        self.default_type_id = self.default_type.get('id', None)
        self.ref_object_type = attr_file.get('referenceObjectType', {})
        self.ref_object_type_schema_id = self.ref_object_type.get('objectSchemaId', None)
        self.ref_object_type_id = self.ref_object_type.get('id', None)
        self.ref_type = attr_file.get('referenceType', {})
        self.ref_type_id = self.ref_type.get('id', None)


def main():
    def json_to_file(dict_content, file):
        a_file = open(file, "w")
        json.dump(dict_content, a_file, indent=4)
        a_file.close()


    def backup(insight, schema_key, data_dir):
        schema_dir_path = f'{data_dir}/{schema_key}'
        try:
            os.mkdir(schema_dir_path, mode=0o755, dir_fd=None)
        except FileExistsError:
            pass

        # Save schema
        schema = insight.get_schema_by_key(schema_key)
        schema_file_path = f"{schema_dir_path}/schema.json"
        json_to_file(schema, schema_file_path)

        # Save schema object types
        schema_id = insight.get_schema_id(schema_key)
        objecttypes = insight.get_schema_objecttypes(schema_id)
        objecttypes_file_path = f"{schema_dir_path}/objecttypes.json"
        json_to_file(objecttypes, objecttypes_file_path)

        # Save schema attributes
        attributes = []
        for objtype in objecttypes:
            attributes_api = insight.get_objtype_attributes(objtype['id'])
            attributes = attributes + attributes_api
        attributes_file_path = f"{schema_dir_path}/attributes.json"
        json_to_file(attributes, attributes_file_path)

    def restore(insight, schema_keys, data_dir, test_mode=True):
        def read_json_file(path):
            with open(path) as f:
                data = json.load(f)
            return data

        # restore schemas
        # Initialization
        schemas = Schemas()
        for schema_key in schema_keys:
            if test_mode:
                schema_key = f"{schema_key}X"
                schema_dir = f"{data_dir}/{schema_key.split('X')[0]}"
            schema_file = read_json_file(f"{schema_dir}/schema.json")
            schema = Schema(schema_file)
            #schemas.schemas[schema_key] = schema_file
            objecttypes_file = read_json_file(f"{schema_dir}/objecttypes.json")
            for objecttype_file in objecttypes_file:
                object_type = ObjectType(objecttype_file)
                schema.object_types[object_type.id] = object_type
                attrs_file = read_json_file(f"{schema_dir}/attributes.json")
                for attr_file in attrs_file:
                    if attr_file['objectType']['id'] == object_type.id:
                        attr = Attribute(attr_file)
                        object_type.attributes.append(attr)
            schemas.schemas[schema_key] = schema
            if test_mode:
                schemas.schemas[schema_key].key = schema_key

        for schema_key in schemas.schemas:
            schema = schemas.schemas[schema_key]

            print(f"schema: {schema.key}")
            try:
                data = {
                    "name": f"{schema.name} test",
                    "objectSchemaKey": schema.key,
                    "description": schema.description
                }
            except KeyError:
                data = {
                    "name": f"{schema.name} test",
                    "objectSchemaKey": schema.key,
                }
            schema_exists = insight.get_schema_by_key(schema.key)
            if schema_exists:
                print(f"Schema {schema.key} exists. Skipping schema for restoring")
            else:
                response = insight.create_schema(data)

            schema.api_id = insight.get_schema_by_key(schema.key)['id']
            insight.allow_other_schemas(schema.api_id)

            # restore object types
            def create_objtype(objtype):
                name = objtype.name
                icon_id = objtype.icon_id
                data = {
                        "name": name,
                        "iconId": icon_id,
                        "objectSchemaId": schema.api_id
                }
                if objtype.parent_id:
                    parent_objtype = schema.object_types[objtype.parent_id]
                    objecttypes_api = insight.get_schema_objecttypes(schema.api_id)
                    objtype_names_api = [objtype_api['name'] for objtype_api in objecttypes_api]
                    # create parent
                    if name not in objtype_names_api:
                        if parent_objtype.name not in objtype_names_api:
                            create_objtype(parent_objtype)
                            objecttypes_api = insight.get_schema_objecttypes(schema.api_id)
                            for objecttype_api in objecttypes_api:
                                if objecttype_api['name'] == parent_objtype.name:
                                    data['parentObjectTypeId'] = objecttype_api['id']
                                    api_id = insight.create_objecttype(data)
                                    objtype.api_id = api_id
                        else:
                            for objecttype_api in objecttypes_api:
                                if objecttype_api['name'] == parent_objtype.name:
                                    data['parentObjectTypeId'] = objecttype_api['id']
                                    api_id = insight.create_objecttype(data)
                                    objtype.api_id = api_id
                else:
                    objecttypes_api = insight.get_schema_objecttypes(schema.api_id)
                    if name not in [objtype_api['name'] for objtype_api in objecttypes_api]:
                        api_id = insight.create_objecttype(data)
                        objtype.api_id = api_id


            for objtype in schema.object_types.values():
                objecttypes_api = insight.get_schema_objecttypes(schema.api_id)
                if objtype.name not in [objtype_api['name'] for objtype_api in objecttypes_api]:
                    create_objtype(objtype)
                else:
                    objtype.api_id = [objtype_api['id'] for objtype_api in objecttypes_api if objtype.name == objtype_api['name']][0]
                    print(f"Skip creating object type {objtype.name}, id: {objtype.api_id}")

        # restore object type attributes
        def create_attr(attr):
            pass



        for schema in schemas.schemas.values():
            print(f"SCHEMA: {schema.name}, ID: {schema.api_id}")
            for object_type in schema.object_types.values():
                print(f"OBJECT TYPE: {object_type.name}, ID: {object_type.api_id}")
                for attr in [attr for attr in object_type.attributes if attr.name not in ("Key", "Name", "Created", "Updated")]:
                    print(f"ATTRIBUTE: {attr.name}")
                    data = {
                            "name": attr.name,
                            "label": attr.label,
                            "description": attr.description,
                            "type": attr.type
                    }
                    if attr.type == 0:
                        data['defaultTypeId'] = attr.default_type_id
                    elif attr.type == 1:
                        for schema in schemas.schemas.values():
                            if schema.id == attr.ref_object_type_schema_id:
                                data['typeValue'] = schema.object_types[attr.ref_object_type_id].api_id
                                data['additionalValue'] = attr.ref_type_id
                                break
                    attrs_api = insight.get_objtype_attributes(object_type.api_id)
                    if attr.name not in [attr['name'] for attr in attrs_api]:
                        insight.create_objecttype_attr(object_type.api_id, data)





    insight = InsightSchema(username=username,password=password)
    if action == "backup":
        for schema_key in schema_keys:
            backup(insight, schema_key, data_dir)
    if action == "restore":
        restore(insight, schema_keys, data_dir, test_mode=True)



if __name__ == '__main__':
    main()
