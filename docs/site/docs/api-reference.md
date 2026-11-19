---
hide:
  - navigation
  - toc
---

# API reference

Every endpoint of the BioID REST API, with its parameters, answers and errors.
**Try it out** works directly on this page: each call is pre-filled with the
trypsin example run, and the examples are that run's real answers. For the
workflow and the concepts behind it, read the [REST API guide](rest-api.md).
The OpenAPI document is at
[/openapi.json](https://bioid-ceitec.dyn.cloud.e-infra.cz/openapi.json), for
generating clients.

<div id="swagger-ui"></div>

<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css">
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script>
<script>
  window.addEventListener("load", function () {
    SwaggerUIBundle({
      url: "https://bioid-ceitec.dyn.cloud.e-infra.cz/openapi.json",
      dom_id: "#swagger-ui",
      deepLinking: true,
      docExpansion: "list",
      defaultModelsExpandDepth: 0,
      defaultModelExpandDepth: 2,
      displayRequestDuration: true,
      filter: true,
      tryItOutEnabled: true,
    });
  });
</script>
<style>
  /* the API's own title and description repeat this page's introduction */
  #swagger-ui .information-container { display: none; }
  #swagger-ui .scheme-container { box-shadow: none; padding: 0; }
</style>
