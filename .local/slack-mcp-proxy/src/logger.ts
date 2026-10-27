import pino, {
  type ChildLoggerOptions,
  type DestinationStream,
  type Logger,
  type LoggerOptions,
} from 'pino';

import { sanitizeLogMetadata } from './sanitize.js';

export type AppLogger = Logger;

const isPrettyLoggingEnabled = process.stdout.isTTY && process.env.NODE_ENV !== 'production';

const transport = isPrettyLoggingEnabled
  ? pino.transport({
      targets: [
        {
          target: 'pino-pretty',
          options: {
            colorize: true,
            translateTime: 'SYS:standard',
            ignore: 'pid,hostname',
          },
        },
      ],
    })
  : undefined;

export function createRootLogger(level: string, destination?: DestinationStream): AppLogger {
  const loggerOptions: LoggerOptions = {
    level,
    base: undefined,
    formatters: {
      bindings: sanitizeLogMetadata,
      log: sanitizeLogMetadata,
    },
  };

  const logger = pino(loggerOptions, destination ?? transport);
  const child = logger.child;
  // Pino intentionally resets bindings formatters for children; filter before serialization.
  logger.child = function <ChildCustomLevels extends string = never>(
    this: AppLogger,
    bindings: Record<string, unknown>,
    options?: ChildLoggerOptions<ChildCustomLevels>,
  ): Logger<ChildCustomLevels, boolean> {
    return Reflect.apply(child, this, [sanitizeLogMetadata(bindings), options]) as Logger<
      ChildCustomLevels,
      boolean
    >;
  };

  return logger;
}

export function createLogger(rootLogger: AppLogger, bindings?: Record<string, unknown>): AppLogger {
  if (!bindings) {
    return rootLogger;
  }

  return rootLogger.child(sanitizeLogMetadata(bindings));
}
