# Application Plugin Authoring

An application plugin is a build-selected registration unit around the workflow-neutral Agent Core. The generic shell loads only the `registration_entry` values present in its compiled `bundle-plan.json`; an unselected plugin is not imported.

## Manifest

Each application declares a JSON-safe manifest with `application_id`, `version`, `api_version`, `distribution_id`, `registration_entry`, `requires`, `conflicts`, `capabilities`, `permission_categories`, `prompt_resources`, `toolset_ids`, `context_provider_ids`, `workflow_state_namespace`, `shell_contribution_ids`, `runtime_requirements`, and `asset_ids`. Permission categories describe policy inputs; they never grant permission. Runtime requirements and assets are selected by the bundle plan.

`registration_entry` has the form `package.module:register_application`. The callable receives the focused application registrar and may add a workflow-neutral `ApplicationRuntimeContribution`, extensions, prompt/context providers, or shell contributions. A runtime contribution supplies the application id/label, runtime definition factory, application state/profile factory, workspace contribution factory, workflow package ids, capabilities, and empty-state metadata. It must not expose a Host or product object. The callable returns a `dispose` callable, or the registrar returns one for each registration. Disposal is reverse ordered and must release every source-owned registration.

## Generic Example

The generic product shell is registered by `embedagent.product_catalog:register`. It owns the workflow-neutral shell contribution and the generic application runtime contribution; it depends only on Core, Protocol, and Host. It does not import the C/C++ workflow package or the build-time composition package.

## C/C++ Example

The C/C++ package exposes `embedagent_workflow_cpp.application:register_application`. Its manifest is owned by `embedagent-workflow-cpp`, requires only public Core/Protocol contracts, and declares Clang/Ctags runtime requirements. Registration adds one C/C++ `ApplicationRuntimeContribution` plus the `CHarnessWorkflowExtension`, C/C++ prompt and context providers, workspace detectors, and workflow shell commands under source id `embedagent.workflow.cpp`. It must not import `embedagent.product_catalog`, product Host bootstrap, or `embedagent_composition`.

## Constraints

Plugins may contribute behavior only through the registrar and declared extension capabilities. They must not mutate Core session truth, own durable restore policy, grant permissions, install packages at runtime, or call remote registries. Runtime assets belong in `scripts/offline-assets.json` and executable requirements belong in `scripts/offline-runtime-contract.json`. A plugin intended for a future independent repository must pass its Core/Protocol isolation tests without importing the product shell.

The minimum test matrix is: manifest validation, registration/disposal order, selected-plan import isolation, wheel dependency/file ownership checks, and offline smoke for the selected closure. C/C++ adds bundle-local Clang/Ctags and workflow evidence only when its plan selects those capabilities.
