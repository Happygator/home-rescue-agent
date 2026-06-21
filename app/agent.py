# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import google.auth
from google.adk.apps import App

from appliance_fixer.agent import root_agent
from appliance_fixer.tools import load_key

# Resolve Gemini API Key from GEMINI_KEY.txt or environments
try:
    key = load_key()
    if key:
        os.environ["GEMINI_API_KEY"] = key
        os.environ["GOOGLE_API_KEY"] = key
except Exception:
    pass

# Direct ADK to use AI Studio endpoint
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "False"

# Gracefully retrieve GCP project ID without raising credentials errors
try:
    _, project_id = google.auth.default()
    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
except Exception:
    if "GOOGLE_CLOUD_PROJECT" not in os.environ:
        os.environ["GOOGLE_CLOUD_PROJECT"] = "appliance-fixer-dev"

# Expose app for Fast API and agents-cli runtime
app = App(
    root_agent=root_agent,
    name="app",
)
