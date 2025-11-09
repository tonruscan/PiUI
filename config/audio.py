"""Audio configuration for UI playback and sample rendering."""

# Preferred output device selection
PREFERRED_AUDIO_DEVICE_NAME = "snd_rpi_justboom_dac, JustBoom DAC HiFi pcm512x-hifi-0"
PREFERRED_AUDIO_DEVICE_INDEX = None
PREFERRED_AUDIO_DEVICE_KEYWORDS = ("snd_rpi_justboom_dac", "justboom", "dac")
FORCE_AUDIO_DEVICE = True  # False to let SDL choose the output device when forcing config
PREFERRED_AUDIO_DEVICE_FALLBACK = (
	"snd_rpi_justboom_dac, JustBoom DAC HiFi pcm512x-hifi-0",
	"justboom",
	"dac",
)

# Mixer initialisation parameters
SAMPLE_RATE = 48000
SAMPLE_SIZE = -16  # Signed 16-bit
CHANNELS = 2
BUFFER_SIZE = 256
MIXER_NUM_CHANNELS = 16
ALLOW_AUDIO_CHANGES = None  # None = SDL default, 0 = enforce exact settings, see pygame.mixer docs
FORCE_AUDIO_CONFIG = True  # True to force Drumbo to reinit mixer with these settings even if already active
