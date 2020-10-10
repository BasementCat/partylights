# PartyLights

Audio reactive lighting control

## Requirements:

  * Python 3.6 on Mac OS X (tested on Catalina) or Linux (Windows may work but is untested)
  * For PyAudio capture:
    * Linux: portaudio19-dev
    * Mac OS: portaudio (from brew)
  * A virtual environment is recommended

## Setup:

  1. Check out the code, and create and activate a virtual environment (if desired)
  2. Install dependencies as noted above
  3. Run `pip install -r requirements/<app>.txt` for whatever components of the application you'll be running (audiocapture, lightserver, mapper, webgui)
    - In development, you can install from `requirements/dev.txt` to install all requirements
  4. Install one of the audio capture requirements files:
    - audiocapture-alsa-all.txt for ALSA
    - audiocapture-pa-linux.txt for PyAudio on Linux
    - audiocapture-pa-macos.txt for PyAudio on Mac OS
  5. Copy the config-example folder to config, and edit the config files as desired
  6. Run the applications: `app/bin/partylights <app>`
