# Coral Smart Birdfeeder
A smart birdfeeder that uses the Coral Enterprise Board + Pi Zero W with camera as a RTSP video source in the feeder,
and identifies the birds that use the feeder. 

### to-do
-[] daemonize python detection script
-[] build bird specific model
-[] image cleanup process
-[] video loss recovery
-[] power down at night, up in the morning
    - can be based off light sensor
-[] focus lense closer to feeder
-[] solar power for pi zero
-[x] better resolution snapshot
    - inference at low res and have high res for snapshot




## License
Copyright 2019 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
