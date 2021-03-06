import os
from typing import Union, List, Optional
from urllib.parse import quote

from pydantic import BaseModel, HttpUrl, root_validator, Field, validator, Extra
from pypads.model.models import ResultType, BaseIdModel, BackendObjectModel, EntryModel, AbstractionType
from pypads.utils.logging_util import FileFormats
from pypads.utils.util import persistent_hash

from pypads_onto.arguments import ontology_uri

DEFAULT_CONTEXT = {
    "@context": {
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "padre": f"{ontology_uri}",
        "uri": "@id",
        "is_a": "@type",
        "experiment": {
            "@id": f"{ontology_uri}contained_in",
            "@type": f"{ontology_uri}Experiment"
        },
        "run": {
            "@id": f"{ontology_uri}contained_in",
            "@type": f"{ontology_uri}Run"
        },
        "created_at": {
            "@id": f"{ontology_uri}created_at",
            "@type": "http://www.w3.org/2001/XMLSchema#dateTime"
        },
        "name": {
            "@id": f"{ontology_uri}label",
            "@type": "http://www.w3.org/2001/XMLSchema#string"
        },
        "in_context": {
            "@id": f"{ontology_uri}relates_to",
            "@type": f"{ontology_uri}Context"
        },
        "reference": {
            "@id": f"{ontology_uri}represents",
            "@type": "http://www.w3.org/2001/XMLSchema#string"
        },
        "produced_by": {
            "@id": f"{ontology_uri}produced_by",
            "@type": f"{ontology_uri}LoggerCall"
        },
        "failed": {
            "@id": f"{ontology_uri}failure",
            "@type": "http://www.w3.org/2001/XMLSchema#boolean"
        }
    }
}
default_ctx_path = None


def get_default_ctx_path():
    """
    Function to persist the default context and get it's location.
    :return:
    """
    try:
        global default_ctx_path
        from pypads.app.pypads import get_current_pads
        pads = get_current_pads()
        if not default_ctx_path:
            obj = pads.schema_repository.get_object(uid=persistent_hash(str(DEFAULT_CONTEXT)))
            default_ctx_path = obj.log_mem_artifact("pypads_context_default", DEFAULT_CONTEXT,
                                                    write_format=FileFormats.json, write_meta=False)
            obj.set_tag("pypads.schema_name", "pypads_context_default")
        return os.path.join(default_ctx_path)
    except Exception as e:
        # Return context itself instead
        return DEFAULT_CONTEXT['@context']


class OntologyModel(BaseModel):
    """
    Object representing an (potential) entry in a knowledge base
    """
    uri: HttpUrl = ...
    context: Union[List[Union[str, dict]], str, dict] = Field(alias='@context', default=None)

    @root_validator
    def add_context(cls, values):
        if ('storage_type' in values
            and values['storage_type'] not in {ResultType.embedded, ResultType.repository_entry}) and not (
                'abstraction_type' in values and values['abstraction_type'] == AbstractionType.reference):
            if values['context'] is None:
                values['context'] = get_default_ctx_path()
            elif isinstance(values['context'], List):
                if len(values['context']) > 0:
                    if values['context'][0] != get_default_ctx_path():
                        values['context'].append(get_default_ctx_path())
            elif values['context'] != get_default_ctx_path():
                values['context'] = [get_default_ctx_path(), values['context']]
        return values


class IdBasedOntologyModel(OntologyModel, BaseIdModel):
    """
    An ontology entry getting its uri build via is_a and id combination.
    """
    is_a: HttpUrl = None
    uri: HttpUrl = None
    category: Optional[str]  # Human readable class representation. This will be converted in ontology entries.
    name: Optional[str]  # Alternative Human readable instance representation.

    @root_validator
    def set_default_uri(cls, values):
        if values['is_a'] is None:
            if 'category' in values and values['category'] is not None:
                values['is_a'] = f"{ontology_uri}{quote(values['category'])}"
            elif 'name' in values and values['name'] is not None:
                values['is_a'] = f"{ontology_uri}{quote(values['name'])}"
            else:
                raise ValueError("Value for is_a is not given and can't be derived")
        if values['uri'] is None:
            values['uri'] = f"{values['is_a']}#{values['uid']}"
        return values

    class Config:
        orm_mode = True


class EmbeddedOntologyModel(IdBasedOntologyModel):
    storage_type: Union[ResultType, str] = None  # This should not be stored into the mongodb
    context: Optional[Union[List[Union[str, dict]], str, dict]]

    @validator('storage_type', pre=True, always=True)
    def default_ts_modified(cls, v, *, values, **kwargs):
        return v or ResultType.embedded
