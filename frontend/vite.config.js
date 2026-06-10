import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { createReadStream, existsSync, statSync } from "node:fs";
import { extname, join, normalize, resolve } from "node:path";

const mahjongFilesDir = resolve("../Mortal/log-viewer/files");
const mimeTypes = {
  ".css": "text/css",
  ".gif": "image/gif",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".js": "text/javascript",
  ".png": "image/png",
  ".txt": "text/plain",
};

function mahjongAssetsPlugin() {
  return {
    name: "mahjong-assets",
    configureServer(server) {
      server.middlewares.use("/mahjong-assets", (req, res, next) => {
        const requestPath = decodeURIComponent((req.url || "").split("?")[0]);
        const filePath = normalize(join(mahjongFilesDir, requestPath));
        const root = normalize(mahjongFilesDir);

        if (!filePath.toLowerCase().startsWith(root.toLowerCase()) || !existsSync(filePath)) {
          next();
          return;
        }

        const stat = statSync(filePath);
        if (!stat.isFile()) {
          next();
          return;
        }

        res.setHeader("Content-Type", mimeTypes[extname(filePath).toLowerCase()] || "application/octet-stream");
        createReadStream(filePath).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [vue(), mahjongAssetsPlugin()],
});
