const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("panelcraftDesktop", {
  platform: process.platform,
  arch: process.arch,
  isDesktop: true,
});
