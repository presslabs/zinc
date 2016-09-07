# zinc
Route 53 zone manager.

zinc provides a simple REST API for managing zones hosted using Amazon Route 53. A presentation of the API endpoints and more specifications is available in the [blueprint](https://github.com/PressLabs/zinc/blob/master/blueprint.apib).

Install [Aglio](https://github.com/danielgtaylor/aglio) in order to view an HTML rendering of the documentation. This can be done in two ways:

* Render a static HTML file by going into the zinc repository and running the command `aglio -i blueprint.apib -o blueprint.html`
* Start a local server at `localhost:3000` by going into the zinc repository and running the command `aglio -i blueprint.apib -s`
