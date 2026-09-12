#!/usr/bin/env node
"use strict";
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Sebastian Bittrich <sebastian.bittrich@rcsb.org>
 */
Object.defineProperty(exports, "__esModule", { value: true });
const tslib_1 = require("tslib");
const compression_1 = tslib_1.__importDefault(require("compression"));
const express_1 = tslib_1.__importDefault(require("express"));
const version_1 = require("./version");
const config_1 = require("./config");
const console_logger_1 = require("../../mol-util/console-logger");
const performance_monitor_1 = require("../../mol-util/performance-monitor");
const web_api_1 = require("./web-api");
function setupShutdown() {
    if (config_1.MembraneServerConfig.shutdownTimeoutVarianceMinutes > config_1.MembraneServerConfig.shutdownTimeoutMinutes) {
        console_logger_1.ConsoleLogger.log('Server', 'Shutdown timeout variance is greater than the timer itself, ignoring.');
    }
    else {
        let tVar = 0;
        if (config_1.MembraneServerConfig.shutdownTimeoutVarianceMinutes > 0) {
            tVar = 2 * (Math.random() - 0.5) * config_1.MembraneServerConfig.shutdownTimeoutVarianceMinutes;
        }
        const tMs = (config_1.MembraneServerConfig.shutdownTimeoutMinutes + tVar) * 60 * 1000;
        console.log(`----------------------------------------------------------------------------`);
        console.log(`  The server will shut down in ${performance_monitor_1.PerformanceMonitor.format(tMs)} to prevent slow performance.`);
        console.log(`  Please make sure a daemon is running that will automatically restart it.`);
        console.log(`----------------------------------------------------------------------------`);
        console.log();
        setTimeout(() => {
            console_logger_1.ConsoleLogger.log('Server', `Shut down due to timeout.`);
            process.exit(0);
        }, tMs);
    }
}
(0, config_1.configureServer)();
function startServer() {
    const app = (0, express_1.default)();
    app.use((0, compression_1.default)({
        level: 6, memLevel: 9, chunkSize: 16 * 16384,
        filter: (req, res) => {
            const ct = res.getHeader('Content-Type');
            if (typeof ct === 'string' && ct.indexOf('tar+gzip') > 0)
                return false;
            return true;
        }
    }));
    (0, web_api_1.initWebApi)(app);
    const port = process.env.port || config_1.MembraneServerConfig.defaultPort;
    app.listen(port).setTimeout(config_1.MembraneServerConfig.requestTimeoutMs);
    console.log(`Mol* Membrane Server ${version_1.VERSION}`);
    console.log(``);
    console.log(`The server is running on port ${port}.`);
    console.log(``);
}
startServer();
if (config_1.MembraneServerConfig.shutdownTimeoutMinutes > 0) {
    setupShutdown();
}
