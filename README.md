# AI-voice-assistants

This Python application creates an interactive voice AI assistant using Google's Gemini 2.0 Flash API. The bot can see (via webcam), hear (via microphone), and speak (via your speakers), providing a natural conversation experience with customizable personas.

## Features

- Real-time voice interaction with Google's Gemini 2.0 Flash AI
- Multiple pre-configured personas (customer care, tech support, sales agent, fitness coach)
- Voice customization with different AI voices
- Optional camera and screen sharing modes
- Text input fallback for typing messages

## Requirements

- Python 3.8+
- Google API key for Gemini

## Installation

1. Clone this repository or download the script:

```bash
git clone https://github.com/HanishDhanwalkar/AI-voice-assistants.git
# or save the script as customer_care.py
```

2. Install required dependencies:

```bash
pip install google-genai opencv-python pyaudio pillow mss
```

3. Set up your Google API key:
   - Get a Gemini API key from [Google AI Studio](https://makersuite.google.com/)
   - Replace the API key in the script or set it as an environment variable

## Usage

### Basic Usage

Run the bot with the default settings:

```bash
python customer_care.py
```

### Command Line Arguments

The script supports several command-line arguments to customize behavior:

```bash
python customer_care.py --mode <mode> --persona <persona> --voice <voice>
```

#### Available Options

- **Mode** (`--mode`):
  - `camera`: Use webcam for visual input (default)
  - `screen`: Share your screen with the AI
  - `none`: Text and audio only, no visual input

- **Persona** (`--persona`):
  - `default`: Standard Gemini behavior
  - `customer_care`: Friendly customer service representative
  - `tech_support`: Technical support specialist
  - `sales_agent`: Product-focused sales representative
  - `fitness_coach`: Motivational fitness instructor

- **Voice** (`--voice`):
  - `Puck`: Default voice (neutral)
  - `Ember`: Alternative voice option
  - `Nova`: Alternative voice option
  - `Echo`: Alternative voice option
  - `Tide`: Alternative voice option

#### Listing Available Options

List all available personas:
```bash
python customer_care.py --list-personas
```

List all available voices:
```bash
python customer_care.py --list-voices
```

### Examples

#### Customer Service Bot

```bash
python customer_care.py --persona customer_care --mode none
```
This creates a voice-only bot that acts as a friendly customer service representative.

#### Technical Support with Camera

```bash
python customer_care.py --persona tech_support --mode camera --voice Nova
```
This creates a bot that can see through your webcam, acts as a technical support specialist, and uses the Nova voice.

#### Fitness Coach

```bash
python customer_care.py --persona fitness_coach --voice Ember
```
This creates a fitness coach bot with an energetic personality using the Ember voice.

## Interaction

Once the bot is running:
1. Speak naturally into your microphone
2. Type text messages at the `message >` prompt
3. Type `q` at the prompt to quit

## Adding Custom Personas

You can add your own personas by modifying the `PERSONAS` dictionary in the script. Each persona is defined by a system prompt that instructs Gemini how to behave.

Example:
```python
PERSONAS = {
    # Existing personas...
    "my_custom_persona": """You are a [describe personality and role].
                         You speak in a [describe speaking style].
                         You frequently use phrases like "[example phrase]" and "[another example phrase]".
                         Your goal is to [describe main objective]."""
}
```

## Troubleshooting

- **No sound output**: Check your speaker settings and make sure the correct output device is selected
- **Microphone not working**: Check your microphone settings and permissions
- **Camera not working**: Check camera permissions and ensure no other application is using the camera
- **API errors**: Verify your API key is correct and has the necessary permissions
- **Performance issues**: Try using the `--mode none` option to reduce resource usage
