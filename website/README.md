# Helix visual explorer

A static companion website for https://github.com/Leowaskin/Helix, designed for
visitors with no technical background. Uses Three.js 0.181.2 (vendored with its
MIT license), plain JavaScript and CSS. No upload service or backend is required.

## Preview

Run `npm run preview` from this directory, then open http://localhost:4173.
Run `npm run check` for JavaScript syntax checks. No npm installation is needed.
The built static files are deliberately tracked in `dist/` for simple hosting.
Optional web fonts come from Google Fonts; system-font fallbacks are provided.

## Scope

The message explorer performs actual naive DNA mapping in the browser. The
constraint comparison implements the Python project's max-run-three byte encoder;
its output was checked against Python for full byte-range, zero and text vectors.
Damage and recovery are explicitly illustrative: the Python RS decoder is not
ported to JavaScript. Repository links point to the full demo and measured results.
All displayed benchmark numbers and the chart come from saved Helix experiments.

The scroll narrative progressively opens the double helix, fades its complementary
strand, and straightens one strand into labeled A/C/G/T bases. Its 24 displayed
bases use the same simple byte mapping as the message explorer. The final caption
explains that base order represents data. This is a conceptual illustration,
not a molecular model or simulation of a physical unzipping process.

The animation reverses when scrolling upward. Pause freezes the model; reduced
motion displays the final strand without an animated transition. Without WebGL,
an SVG and static sequence support the same explanatory captions.
Reduced-motion preferences, a pause control, an SVG fallback and responsive layouts
are included. Browser-rendered interaction and visual QA could not be performed in
this session because no browser-control tool was available.

Sites hosts a private preview; this is not automatically accessible to GitHub visitors.
To serve publicly from GitHub Pages, configure its publishing source to use the
contents of `dist/`, or use another static host. All asset paths are relative so
subdirectory hosting works. This task did not enable public access or push to GitHub.
