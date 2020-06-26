PLUGIN_VERSION=1.1.4
PLUGIN_ID=salesforce

plugin:
	cat plugin.json|json_pp > /dev/null
	rm -rf dist
	mkdir dist
	zip --exclude "*.pyc" -r dist/dss-plugin-${PLUGIN_ID}-${PLUGIN_VERSION}.zip custom-recipes parameter-sets plugin.json python-connectors python-lib
