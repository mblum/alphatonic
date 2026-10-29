---
render_macros: true
---

{# Edit README.md in the repository root. Adapt its links for the site home page. #}
{% filter replace("](docs/", "](") | replace("](CONTRIBUTING.md)", "](contributing/development.md)") | replace("](CHANGELOG.md)", "](changelog.md)") | replace("](LICENSE)", "](https://github.com/mblum/alphatonic/blob/master/LICENSE)") %}
{% include "README.md" %}
{% endfilter %}
