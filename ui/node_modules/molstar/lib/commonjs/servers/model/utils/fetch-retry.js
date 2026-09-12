"use strict";
/**
 * Copyright (c) 2018-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Adam Midlik <midlik@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.fetchRetry = fetchRetry;
exports.wrapFetch = wrapFetch;
const tslib_1 = require("tslib");
const node_fetch_1 = tslib_1.__importStar(require("node-fetch"));
const retry_if_1 = require("../../../mol-util/retry-if");
const google_cloud_storage_1 = require("../../common/google-cloud-storage");
const RETRIABLE_NETWORK_ERRORS = [
    'ECONNRESET', 'ENOTFOUND', 'ESOCKETTIMEDOUT', 'ETIMEDOUT',
    'ECONNREFUSED', 'EHOSTUNREACH', 'EPIPE', 'EAI_AGAIN'
];
function isRetriableNetworkError(error) {
    return error && RETRIABLE_NETWORK_ERRORS.includes(error.code);
}
async function fetchRetry(url, timeout, retryCount, onRetry) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    const signal = controller.signal; // TODO: fix type
    const result = await (0, retry_if_1.retryIf)(() => wrapFetch(url, { signal }), {
        retryThenIf: r => r.status === 408 /** timeout */ || r.status === 429 /** too many requests */ || (r.status >= 500 && r.status < 600),
        // TODO test retryCatchIf
        retryCatchIf: e => isRetriableNetworkError(e),
        onRetry,
        retryCount
    });
    clearTimeout(id);
    return result;
}
/** Like `fetch` but supports Google Cloud Storage (gs://) protocol. */
function wrapFetch(url, init) {
    if (url.startsWith('gs://'))
        return fetchGS(url, init);
    else
        return (0, node_fetch_1.default)(url, init);
}
async function fetchGS(url, init) {
    var _a;
    if ((_a = init === null || init === void 0 ? void 0 : init.signal) === null || _a === void 0 ? void 0 : _a.aborted)
        throw new node_fetch_1.AbortError('The user aborted a request.');
    const data = await (0, google_cloud_storage_1.downloadGs)(url);
    return new node_fetch_1.Response(data, init);
}
