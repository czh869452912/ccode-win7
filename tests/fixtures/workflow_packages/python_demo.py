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
                    "icon_key": "search",
                    "color_token": "info",
                    "command_id": "mode.python-explore",
                },
                {
                    "id": "python-build",
                    "label": "Python Build",
                    "description": "Implement Python code",
                    "icon_key": "hammer",
                    "color_token": "success",
                    "command_id": "mode.python-build",
                },
            ],
            "commands": [
                {
                    "name": "mode.python-build",
                    "usage": "/mode python-build",
                    "summary": "Switch to Python Build mode",
                    "source_type": "mode",
                    "source_id": "python-demo",
                    "active": True,
                }
            ],
            "tools": [
                {
                    "name": "pytest",
                    "label": "Pytest",
                    "icon_key": "test-tube",
                    "renderer_key": "command",
                    "permission_category": "command",
                }
            ],
            "emptyState": {
                "scenario_label": "Python workspace",
                "primary": "Choose a local Python workspace",
                "secondary": "Python workflow metadata drives this shell.",
            },
        }
