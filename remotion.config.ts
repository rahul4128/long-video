import { Config } from "@remotion/cli/config";

Config.setChromiumOpenGlRenderer("angle");
Config.setBrowserExecutable(null);
Config.setOverwriteOutput(true);
Config.setChromiumFlags([
  "--no-sandbox",
  "--disable-setuid-sandbox",
  "--disable-dev-shm-usage",
  "--disable-gpu",
]);
