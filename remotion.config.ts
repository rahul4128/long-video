import { Config } from "@remotion/cli/config";

// Software OpenGL rendering for headless Linux runners
Config.setChromiumOpenGlRenderer("swangle");

// Automatically overwrite output video files
Config.setOverwriteOutput(true);
