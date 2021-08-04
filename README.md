
# WhiteSource API extension
WhiteSource is an open source software scanner to detect and remediate open source security and compliance issues in real-time. It offers multiple integrations for repositories, package managers and so on, further instructions are found [here](https://www.whitesourcesoftware.com/whitesource-integrations/). All those integrations are based on the [Unified Agent](https://whitesource.atlassian.net/wiki/spaces/WD/pages/804814917/Unified+Agent+Configuration+File+and+Parameters) which is written in Java. For end users it is possible to execute the Unified Agent directly.
The whole concept lacks one core feature, include WhiteSource scans in a programmatically way to empower automation.

The whitesource-api-extension tackles this difficulty by providing a websocket based webserver, automatically triggering WhiteSource Unified Agent scans based on sent parameters.

--------


**`WS /component`**
Performs WhiteSource code scan for provided archive.
The protocol expects the data in three segments.

### Segment 1 - Metadata (JSON)
```json
{
  "chunkSize": 1024,
  "length": 14796692
}
```
`chunkSize` tar archive chunk transmission size in bytes

`length` tar archive length in bytes

### Segment 2 - WhiteSource Configuration (JSON)
```json
{
  "apiKey": 1024,
  "extraWsConfig": {...},
  "productToken": "foo",
  "projectName": "foo",
  "requesterEmail": "foo",
  "userKey": "foo",
  "wssUrl": "https://saas.whitesourcesoftware.com/agent"
}
```
*The following keys are mandatory*

`apiKey` WhiteSource documentation lacks consistency, its the equivalent to `organizationKey`

`extraWsConfig` additional parameters are directly parsed into the whitesource-unified-agent configuration file, a detailed documentation can be found [here](https://whitesource.atlassian.net/wiki/spaces/WD/pages/804814917/Unified+Agent+Configuration+File+and+Parameters)

`productToken` specifies product to put project to

`projectName` used as WhiteSource project name

`requesterEmail` who requested the scan

`userKey` used for user authentication

`wss.url` WhiteSource frontend endpoint with `/agent` suffix

`component` archive to be scanned, has to be a tarball

### Segment 3 - To be scanned archive (bytes)
Archive stream in chunks as specified in metadata with the combined length as specified in metadata.

--------

**Image repo `eu.gcr.io/gardener-project/cc/whitesource-api-extension`**
