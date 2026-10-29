---
render_macros: true
---

{# Edit CONTRIBUTING.md in the repository root. #}
{% filter replace("](docs/", "](../") | replace("](README.md)", "](../index.md)") | replace("](CHANGELOG.md)", "](../changelog.md)") %}
{% include "CONTRIBUTING.md" %}
{% endfilter %}
