# Salesforce Plugin

This Dataiku DSS plugin lets you read and write data from / to from your [Salesforce](https://www.salesforce.com) account.

Documentation: https://www.dataiku.com/product/plugins/salesforce/

### Changelog

**Version 1.2.0 (2020-07-21)**

* New: Recipe for writing or updating a Salesforce object
* New: Support two new authentication methods: Username-Password via plugin presets and SSO (OAuth2) with per-user credentials mode
* Fixed: Python 3 comptability

If you upgrade from 1.1.0, the plugin will continue to work. However, at the first edit of the settings of a dataset, you will need to set "Authentication method =  JSON token (legacy)".

**Version 1.1.0 (2017-12-01)**

* Fixed: the number of rows returned by the plugin is now enforced (that fixes an issue with DSS 4.1.0)
* New: Report dataset (beta)

**Version 1.0.0 (2017-06-12)**

* Enhanced: the SOQL query field is now multi-line
* More consistency in the naming of the python-connectors

**Version 0.1.1 "beta 2" (2017-04-18)**

* Fixed: Schema of the output of datasets
* Enhanced: DSS shows an error when not able to refresh the JSON token (recipe)

**Version 0.1.0 "beta 1" (2017-04-03)**

* New: Recipe to refresh the token
* New: The token can be stored in a file. This way, it can be shared by all datasets.
* New: Dataset to get records of an Object
* Enhanced: Clean null values when output format is 'Readable with columns'

**Version 0.0.2 "alpha 2" (2017-02-28)**

* New dataset available: `List View records` and `SOQL query`
* Improved documentation

**Version 0.0.1 "alpha 1" (2017-02-17)**

* Initial release
* Two datasets available: `List objects` and `SOQL query`


## Roadmap

* Debugging! Please submit feedbacks.
* Report: support of other formats (summary and matrix reports) and asynchronous calls

### Licence
This plugin is distributed under the Apache License version 2.0
