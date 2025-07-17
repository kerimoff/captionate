import { nodeResolve } from '@rollup/plugin-node-resolve';
import typescript from '@rollup/plugin-typescript';

export default [
  // UMD build for browsers
  {
    input: 'src/index.ts',
    output: {
      file: 'dist/captionato.js',
      format: 'umd',
      name: 'Captionato',
      exports: 'named'
    },
    plugins: [
      nodeResolve(),
      typescript({
        declaration: true,
        declarationDir: 'dist',
        exclude: ['**/*.test.ts']
      })
    ]
  },
  // ES module build
  {
    input: 'src/index.ts',
    output: {
      file: 'dist/captionato.esm.js',
      format: 'es'
    },
    plugins: [
      nodeResolve(),
      typescript({
        declaration: false,
        exclude: ['**/*.test.ts']
      })
    ]
  }
];