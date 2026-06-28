# docs/.local/

**Private working directory. Contents are gitignored; only this README is committed.**

Part of how this repo is worked: anything genuinely private — strategy notes, personal context, scratch analysis, drafts not meant for the public record — lives in a `.local/` folder (or in `sandbox/`). Git ignores everything inside except this marker, so the private layer is *visible as a convention* without ever exposing its contents.

Clone this repo and this folder is empty by design. That's the point.

**Rule:** `.local/` (at any depth) and `sandbox/` are never committed, except their `README.md` markers. Public, durable content goes everywhere else.
