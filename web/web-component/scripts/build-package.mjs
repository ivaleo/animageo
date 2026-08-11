import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';


const here = path.dirname(fileURLToPath(import.meta.url));
const packageRoot = path.resolve(here, '..');
const sourcePath = path.join(packageRoot, 'src', 'animageo-board.js');
const outputDir = path.join(packageRoot, 'dist');
const outputPath = path.join(outputDir, 'animageo-board.js');

const source = await readFile(sourcePath, 'utf8');
const localImport = "from '../../runtime/src/index.js';";
const packageImport = "from '@animageo/runtime';";

if (!source.includes(localImport)) {
  throw new Error(`Expected local runtime import in ${sourcePath}`);
}

await mkdir(outputDir, { recursive: true });
await writeFile(outputPath, source.replace(localImport, packageImport), 'utf8');
console.log(`Built ${path.relative(packageRoot, outputPath)}`);
