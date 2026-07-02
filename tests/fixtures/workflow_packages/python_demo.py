class PythonDemoWorkflowPackage(object):
    package_id = "workflow-python-demo"
    label = "Python Demo"

    def package_manifest(self):
        return {
            "id": self.package_id,
            "label": self.label,
            "supported_modes": ["python-explore", "python-build"],
            "tools": [
                {
                    "name": "pytest",
                    "label": "Pytest",
                    "renderer_key": "command",
                    "permission_category": "command",
                }
            ],
        }

    def capability_metadata(self):
        return {
            "modes": [
                {
                    "id": "python-explore",
                    "label": "Python Explore",
                    "description": "Inspect Python code",
                    "iconKey": "search",
                    "colorToken": "info",
                    "commandId": "mode.python-explore",
                },
                {
                    "id": "python-build",
                    "label": "Python Build",
                    "description": "Implement Python code",
                    "iconKey": "hammer",
                    "colorToken": "success",
                    "commandId": "mode.python-build",
                },
            ],
            "commands": [
                {
                    "id": "mode.python-build",
                    "label": "Python Build",
                    "group": "mode",
                    "dispatch": {"kind": "mode.set", "mode": "python-build"},
                }
            ],
            "tools": [
                {
                    "name": "pytest",
                    "label": "Pytest",
                    "iconKey": "test-tube",
                    "rendererKey": "command",
                    "permissionCategory": "command",
                }
            ],
            "emptyState": {
                "scenario_label": "Python workspace",
                "primary": "Choose a local Python workspace",
                "secondary": "Python workflow metadata drives this shell.",
            },
        }
