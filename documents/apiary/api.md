FORMAT: 1A
HOST: https://resolution-stage.copyrighthub.org

# Open Permissions Platform - Resolution Service

The resolution service resolves a Hub Key (a URL for an entity such as an Asset) to some top level information regarding the entity.

# Resolution of hubkeys

## Resolution of hub keys s1 [/s1/{hub_id}/{repository_id}/{entity_type}/{entity_id}]

+ Parameters
    + hub_id : `hub01` (string, required) - Identifies the Hub
    + repository_id : `02321abcdef` (string, required) -  Identifies the Repository storing the information
    + entity_type : `asset` (string, required) - The type of the entity referenced by this Hub Key
    + entity_id  :  `0101020020233` (string, required) -  Identifies the entity


### Ressolve a hub key S1 [GET]


+ Request resolve a hub key and get redirected to a page providing information on the asset

+ Response 302


+ Request resolve a hub key and return information associated to provider

    + Headers

            Accept: application/json

+ Response 200 (application/json; charset=UTF-8)

    + Body

             {
                "repository_id": "3eae5d6d42db4f698d37a9763c10b209",
                "entity_id": "aca6e04f94034382b051162f3068d826",
                "entity_type": "asset",
                "hub_id": "hub1",
                "hub_key": "https://resolution:8009/s1/hub1/3eae5d6d42db4f698d37a9763c10b209/asset/aca6e04f94034382b051162f3068d826",
                "schema_version": "s1",
                "provider": {
                    "website": "http://testco.digicat.io",
                    "star_rating": 0,
                    "name": "TestCo",
                    "twitter": "DigiCatapult",
                    "state": "approved",
                    "created_by": "testadmin",
                    "id": "testco",
                    "phone": "0300 1233 101",
                    "reference_links": {
                        "links": {
                            "demoidtype": "http://www.testco.com/"
                        },
                        "redirect_id_type": "demoidtype"
                    },
                    "address": "Digital Catapult\n101 Euston Road London\nNW1 2RA",
                    "email": "exampleco@digicat.io",
                    "description": "A fictional company for testing purposes"
                },
                "resolver_id": "https://resolution:8009"
            }


## Resolution of hub keys S0 [/s0/{hub_id}/{entity_type}/{organisation_id}/{source_id_type}/{source_id}]

+ Parameters
    + hub_id : `hub01` (string, required) - Identifies the Hub
    + entity_type : `asset` (string, required) - Type of entity
    + organisation_id : `acme` (string, required) - Organisation that has provided the asset
    + source_id_type : `ISBN` (string, required) - Type of the source id provided by the organisation
    + source_id  :  `0101020020233` (string, required) -  The actual source id value

### Ressolve a hub key S0 [GET]

Resolve a hub key and redirect to provider page


+ Request resolve a hub key and get redirected to a page providing information on the asset

+ Response 302


+ Request resolve a hub key and return information associated to provider

    + Headers

            Accept: application/json



+ Response 200 (application/json; charset=UTF-8)

    + Body

            {
                "organisation_id": "testco",
                "entity_id": "2996ae7e74ee40f690e34c9d494de747",
                "entity_type": "asset",
                "hub_id": "hub1",
                "hub_key": "https://resolution:8009/s0/hub1/asset/testco/testcopictureid/2996ae7e74ee40f690e34c9d494de747",
                "schema_version": "s0",
                "id_type": "testcopictureid",
                "provider": {
                    "website": "http://testco.digicat.io",
                    "star_rating": 0,
                    "name": "TestCo",
                    "twitter": "DigiCatapult",
                    "state": "approved",
                    "created_by": "testadmin",
                    "id": "testco",
                    "phone": "0300 1233 101",
                    "reference_links": {
                        "links": {
                            "demoidtype": "http://www.testco.com/"
                        },
                        "redirect_id_type": "demoidtype"
                    },
                    "address": "Digital Catapult\n101 Euston Road London\nNW1 2RA",
                    "email": "exampleco@digicat.io",
                    "description": "A fictional company for testing purposes"
                },
                "resolver_id": "https://resolution:8009"
            }


## Invalid hub keys [/s{v}/{something_wrong}]

When the hub key specified is invalid, the resolution service will return a 404 response.


```no-highlight
https://resolution:8009/s1/hub1/3eae5d6d42db4f698d37a9763c10b209/asset/invalidvalue
```

+ Response 404
