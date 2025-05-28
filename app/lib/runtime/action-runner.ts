import { WebContainer } from '@webcontainer/api';
import { map, type MapStore } from 'nanostores';
import * as nodePath from 'node:path';
import type { BoltAction } from '~/types/actions';
import { createScopedLogger } from '~/utils/logger';
import { unreachable } from '~/utils/unreachable';
import type { ActionCallbackData } from './message-parser';
// Add imports for chat history
import { db, chatId } from '~/lib/persistence/useChatHistory';
import { getMessages } from '~/lib/persistence/db';
import type { Message } from 'ai';

const logger = createScopedLogger('ActionRunner');

export type ActionStatus = 'pending' | 'running' | 'complete' | 'aborted' | 'failed';

export type BaseActionState = BoltAction & {
  status: Exclude<ActionStatus, 'failed'>;
  abort: () => void;
  executed: boolean;
  abortSignal: AbortSignal;
};

export type FailedActionState = BoltAction &
  Omit<BaseActionState, 'status'> & {
    status: Extract<ActionStatus, 'failed'>;
    error: string;
  };

export type ActionState = BaseActionState | FailedActionState;

type BaseActionUpdate = Partial<Pick<BaseActionState, 'status' | 'abort' | 'executed'>>;

export type ActionStateUpdate =
  | BaseActionUpdate
  | (Omit<BaseActionUpdate, 'status'> & { status: 'failed'; error: string });

type ActionsMap = MapStore<Record<string, ActionState>>;

type LogEntry = {
  command: string;
  stdout: string;
  stderr: string;
  exitCode: number;
  success: boolean;
  first?: boolean;
  timestamp: number;
};

type BatchContext = {
  messages?: any[];
  files?: any[];
};

export class ActionRunner {
  #webcontainer: Promise<WebContainer>;
  #currentExecutionPromise: Promise<void> = Promise.resolve();

  actions: ActionsMap = map({});

  #logBatch: LogEntry[] = [];
  #logBatchTimer: NodeJS.Timeout | null = null;
  #logBatchDelay = 3000;
  #isProcessingCommands = false;
  #processingEndTimeout: NodeJS.Timeout | null = null;
  #processingEndDelay = 2000;

  constructor(webcontainerPromise: Promise<WebContainer>) {
    this.#webcontainer = webcontainerPromise;
  }

  #markCommandProcessingStart() {
    this.#isProcessingCommands = true;
    if (this.#processingEndTimeout) {
      clearTimeout(this.#processingEndTimeout);
      this.#processingEndTimeout = null;
    }
  }

  #markCommandProcessingEnd() {
    if (this.#processingEndTimeout) {
      clearTimeout(this.#processingEndTimeout);
    }
    this.#processingEndTimeout = setTimeout(() => {
      this.#isProcessingCommands = false;
      this.#sendBatchedLogs();
    }, this.#processingEndDelay);
  }

#addLogToBatch(log: Omit<LogEntry, 'timestamp'>) {
  const entry: LogEntry = { ...log, timestamp: Date.now() };
  if (this.#logBatch.length === 0) entry.first = true;
  this.#logBatch.push(entry);

  if (this.#logBatch.length === 1 && !this.#logBatchTimer) {
    this.#logBatchTimer = setTimeout(() => {
      if (!this.#isProcessingCommands) {
        this.#sendBatchedLogs(); // No context needed for regular timeout
      }
    }, this.#logBatchDelay);
  }
}

  async #sendBatchedLogs(context?: BatchContext) {
  if (this.#logBatchTimer) {
    clearTimeout(this.#logBatchTimer);
    this.#logBatchTimer = null;
  }
  if (this.#logBatch.length === 0) return;

  // Always mark the first and last in the batch
  if (this.#logBatch.length > 0) this.#logBatch[0].first = true;
  if (this.#logBatch.length > 1) this.#logBatch[this.#logBatch.length - 1].first = true;

  // Get chat history and file modifications
  let chatHistory: any[] = [];
  let fileModifications: any = undefined;

  try {
    // Get chat history
    const currentChatId = chatId.get();
    if (db && currentChatId) {
      const storedChat = await getMessages(db, currentChatId);
      if (storedChat && storedChat.messages) {
        chatHistory = storedChat.messages;
      }
    }

    // Get file modifications
    if (typeof window !== 'undefined') {
      const { workbenchStore } = await import('~/lib/stores/workbench');
      await workbenchStore.saveAllFiles();
      fileModifications = workbenchStore.getFileModifcations();
    }
  } catch (error) {
    logger.error('Failed to get context data:', error);
  }

  try {
    await fetch('/api/logs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },

      body: JSON.stringify({
        logs: this.#logBatch.map(({ timestamp, ...rest }) => rest),
        thread_id: crypto.randomUUID(),
        stream: true,
        use_reasoning: true,
        messages: context?.messages || chatHistory,
        files: context?.files || fileModifications,
      }),
    });
    this.#logBatch = [];
  } catch (error) {
    logger.error('Failed to send batched logs:', error);
  }
}

async #sendLogsToBackend(logData: {
  command: string;
  stdout: string;
  stderr: string;
  exitCode: number;
}) {
  try {
    console.log('🔍 sendLogsToBackend called with:', logData);
    
    // Filter out false positives
    if (this.#isFalsePositiveError(logData)) {
      console.log('⚠️ Skipping false positive:', logData.command);
      logger.debug(`Skipping false positive: ${logData.command}`);
      this.#markCommandProcessingEnd();
      return;
    }
    
    console.log('✅ Adding log to batch:', {
      command: logData.command,
      success: logData.exitCode === 0,
      exitCode: logData.exitCode
    });
    
    // Add to batch (success if exitCode === 0)
    this.#addLogToBatch({
      ...logData,
      success: logData.exitCode === 0,
    });
    this.#markCommandProcessingEnd();
  } catch (error) {
    console.error('❌ Failed to process logs:', error);
    logger.error('Failed to process logs:', error);
    this.#markCommandProcessingEnd();
  }
}

  #isFalsePositiveError(logData: {
    command: string;
    stdout: string;
    stderr: string;
    exitCode: number;
  }): boolean {
    if (logData.command.includes('curl') && logData.stdout.includes('% Total') && logData.stdout.includes('0 --:--:--')) {
      return true;
    }
    return false;
  }


  async #runFileAction(action: ActionState) {
    if (action.type !== 'file') {
      unreachable('Expected file action');
    }

    const webcontainer = await this.#webcontainer;

    let folder = nodePath.dirname(action.filePath);

    // remove trailing slashes
    folder = folder.replace(/\/+$/g, '');

    if (folder !== '.') {
      try {
        await webcontainer.fs.mkdir(folder, { recursive: true });
        logger.debug('Created folder', folder);
      } catch (error) {
        logger.error('Failed to create folder\n\n', error);
      }
    }

    try {
      await webcontainer.fs.writeFile(action.filePath, action.content);
      logger.debug(`File written ${action.filePath}`);
    } catch (error) {
      logger.error('Failed to write file\n\n', error);
    }
  }


  #updateAction(id: string, newState: ActionStateUpdate) {
    const actions = this.actions.get();

    this.actions.setKey(id, { ...actions[id], ...newState });
  }

  addAction(data: ActionCallbackData) {
    const { actionId } = data;

    const actions = this.actions.get();
    const action = actions[actionId];

    if (action) {
      // action already added
      return;
    }

    const abortController = new AbortController();

    this.actions.setKey(actionId, {
      ...data.action,
      status: 'pending',
      executed: false,
      abort: () => {
        abortController.abort();
        this.#updateAction(actionId, { status: 'aborted' });
      },
      abortSignal: abortController.signal,
    });

    this.#currentExecutionPromise.then(() => {
      this.#updateAction(actionId, { status: 'running' });
    });
  }

  async runAction(data: ActionCallbackData) {
    const { actionId } = data;
    const action = this.actions.get()[actionId];

    if (!action) {
      unreachable(`Action ${actionId} not found`);
    }

    if (action.executed) {
      return;
    }

    this.#updateAction(actionId, { ...action, ...data.action, executed: true });

    this.#currentExecutionPromise = this.#currentExecutionPromise
      .then(() => {
        return this.#executeAction(actionId);
      })
      .catch((error) => {
        console.error('Action failed:', error);
      });
  }

  async #executeAction(actionId: string) {
    const action = this.actions.get()[actionId];

    this.#updateAction(actionId, { status: 'running' });

    try {
      switch (action.type) {
        case 'shell': {
          await this.#runShellAction(action);
          break;
        }
        case 'file': {
          await this.#runFileAction(action);
          break;
        }
      }

      this.#updateAction(actionId, { status: action.abortSignal.aborted ? 'aborted' : 'complete' });
    } catch (error) {
      this.#updateAction(actionId, { status: 'failed', error: 'Action failed' });

      // re-throw the error to be caught in the promise chain
      throw error;
    }
  }

async #runShellAction(action: ActionState) {
  if (action.type !== 'shell') {
    unreachable('Expected shell action');
  }

  console.log('🐚 Starting shell action:', action.content);
  this.#markCommandProcessingStart();

  const webcontainer = await this.#webcontainer;
  let stdout = '';
  let stderr = '';

  const process = await webcontainer.spawn('jsh', ['-c', action.content], {
    env: { npm_config_yes: true },
  });

  action.abortSignal.addEventListener('abort', () => {
    process.kill();
  });

  // Check if this is a long-running command
  const isLongRunningCommand = this.#isLongRunningCommand(action.content);
  let logsAlreadySent = false;

  // Capture stdout
  process.output.pipeTo(
    new WritableStream({
      write: (data) => {
        stdout += data;
//        console.log('📤 stdout:', data);
        
        // For long-running commands, send logs when we detect startup completion
        if (isLongRunningCommand && !logsAlreadySent && this.#detectStartupComplete(stdout, action.content)) {
          console.log('🚀 Long-running process startup detected - sending logs');
          logsAlreadySent = true;
          this.#sendLogsToBackend({
            command: action.content,
            stdout,
            stderr,
            exitCode: 0, // Assume success for started processes
          });
        }
      },
    }),
  );

  // Capture stderr if available
  if (process.stderr) {
    process.stderr.pipeTo(
      new WritableStream({
        write(data) {
          stderr += data;
//          console.error('📤 stderr:', data);
        },
      }),
    );
  }

  if (isLongRunningCommand) {
    console.log('🔄 Long-running command detected, not waiting for exit');
    // For long-running commands, we'll either send logs on startup detection
    // or after a brief delay to capture initial output
    if (!logsAlreadySent) {
      setTimeout(async () => {
        if (!logsAlreadySent) {
          console.log('⏰ Sending logs for long-running process after delay');
          await this.#sendLogsToBackend({
            command: action.content,
            stdout,
            stderr,
            exitCode: 0,
          });
        }
      }, 5000); // 5 second delay for initial output
    }
  } else {
    // For regular commands, wait for completion
    try {
      const exitCode = await process.exit;
      console.log('🏁 Process finished with exit code:', exitCode);

      // Send logs to backend
      console.log('📤 About to send logs to backend...');
      await this.#sendLogsToBackend({
        command: action.content,
        stdout,
        stderr,
        exitCode,
      });

      logger.debug(`Process terminated with code ${exitCode}`);
    } catch (error) {
      console.error('❌ Process error:', error);
      await this.#sendLogsToBackend({
        command: action.content,
        stdout,
        stderr,
        exitCode: 1,
      });
    }
  }
}

#isLongRunningCommand(command: string): boolean {
  const longRunningPatterns = [
    'npm run dev',
    'npm start',
    'yarn dev', 
    'yarn start',
    'pnpm dev',
    'pnpm start',
    'vite',
    'next dev',
    'serve',
    'http-server',
    'live-server',
    'webpack serve',
    'ng serve',
    'vue serve',
  ];
  
  return longRunningPatterns.some(pattern => 
    command.toLowerCase().includes(pattern.toLowerCase())
  );
}

#detectStartupComplete(output: string, command: string): boolean {
  // Detect when dev servers have started successfully
  const startupIndicators = [
    'local:',
    'ready in',
    'ready on', 
    'listening on',
    'server running',
    'compiled successfully',
    'build completed',
    'dev server running',
    'development server',
    'server started',
    'available on:',
    'localhost:',
    'http://',
    'https://',
  ];
  
  const lowerOutput = output.toLowerCase();
  return startupIndicators.some(indicator => 
    lowerOutput.includes(indicator.toLowerCase())
  );
}
}
