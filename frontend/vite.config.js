import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { createReadStream, cpSync, existsSync, statSync } from 'node:fs';
import { resolve, sep } from 'node:path';

const geoRoot = resolve('node_modules/@countrystatecity/countries-browser/dist/data');

function localGeoData() {
  return {
    name: 'local-geo-data',
    configureServer(server) {
      server.middlewares.use('/geo/data', (request, response, next) => {
        const filename = resolve(geoRoot, decodeURIComponent(request.url || '').split('?')[0].replace(/^\//, ''));
        if (!filename.startsWith(geoRoot + sep) || !filename.endsWith('.json') || !existsSync(filename) || !statSync(filename).isFile()) return next();
        response.setHeader('Content-Type', 'application/json; charset=utf-8');
        response.setHeader('Cache-Control', 'public, max-age=86400');
        createReadStream(filename).pipe(response);
      });
    },
    closeBundle() {
      cpSync(geoRoot, resolve('dist/geo/data'), { recursive: true });
    },
  };
}

export default defineConfig({ plugins: [react(), localGeoData()] });
