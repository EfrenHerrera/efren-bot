import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

const script = `
import { createRootLogger } from './build/logger.js';
const root = createRootLogger('trace');
const logger = root.child({component:'callback', authorization:'private-marker', nested:{code:'private-marker'}}).child({cookie:'private-marker'});
logger.info({method:'POST',path:'/callback',status:200,headers:{cookie:'private-marker'},body:'private-marker'}, 'Compiled callback event');
logger.error({method:'POST',path:'/oauth/token',status:502,message:'https://private-user:private-password@example.test/?code=private-marker#private-fragment',err:new Error('private-marker')}, 'Compiled failure event');
`;
const result = spawnSync(process.execPath, ['--input-type=module', '-e', script], {
  encoding: 'utf8', timeout: 10000, env: { PATH: process.env.PATH, NODE_ENV: 'production' },
});
assert.equal(result.status, 0, result.stderr);
assert.equal(result.stderr, '');
assert.doesNotMatch(result.stdout, /private/);
const lines = result.stdout.trim().split('\n').map(JSON.parse);
assert.equal(lines.length, 2);
assert.equal(lines[0].method, 'POST');
assert.equal(lines[0].path, '/callback');
assert.equal(lines[0].status, 200);
assert.equal(lines[0].component, 'callback');
assert.equal(lines[1].status, 502);
assert.equal(lines[1].level, 50);
console.log(JSON.stringify({ compiled_stdout_check: 'passed', line_count: lines.length, secrets_found: false, server_started: false }));
