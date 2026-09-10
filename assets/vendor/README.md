# Vendored chart libraries

These files are copied verbatim from npm so the dashboard has no runtime
dependency on a third-party CDN (the page keeps working on a restricted
network, and nothing about the firm's browsing is sent to an external host).

| File | Package | Version | Licence |
|---|---|---|---|
| `chart.umd.js` | [chart.js](https://www.npmjs.com/package/chart.js) | 4.4.7 | MIT |
| `chartjs-adapter-date-fns.bundle.min.js` | [chartjs-adapter-date-fns](https://www.npmjs.com/package/chartjs-adapter-date-fns) | 3.0.0 | MIT (bundles date-fns, MIT) |

To refresh:

```bash
npm pack chart.js@<version> chartjs-adapter-date-fns@<version>
tar xzf chart.js-<version>.tgz && cp package/dist/chart.umd.js assets/vendor/chart.umd.js
tar xzf chartjs-adapter-date-fns-<version>.tgz \
  && cp package/dist/chartjs-adapter-date-fns.bundle.min.js assets/vendor/
```
