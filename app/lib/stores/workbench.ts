import { atom, map, type MapStore, type ReadableAtom, type WritableAtom } from 'nanostores';
import type { EditorDocument, ScrollPosition } from '~/components/editor/codemirror/CodeMirrorEditor';
import { ActionRunner } from '~/lib/runtime/action-runner';
import type { ActionCallbackData, ArtifactCallbackData } from '~/lib/runtime/message-parser';
import { webcontainer } from '~/lib/webcontainer';
import type { ITerminal } from '~/types/terminal';
import { unreachable } from '~/utils/unreachable';
import { EditorStore } from './editor';
import { FilesStore, type FileMap } from './files';
import { PreviewsStore } from './previews';
import { TerminalStore } from './terminal';
import { db, chatId } from '~/lib/persistence/useChatHistory';
import { getMessages } from '~/lib/persistence/db';
import type { File } from './files';

export interface ArtifactState {
  id: string;
  title: string;
  closed: boolean;
  runner: ActionRunner;
}

export type ArtifactUpdateState = Pick<ArtifactState, 'title' | 'closed'>;

type Artifacts = MapStore<Record<string, ArtifactState>>;

export type WorkbenchViewType = 'code' | 'preview';

export class WorkbenchStore {
  #previewsStore = new PreviewsStore(webcontainer);
  #filesStore = new FilesStore(webcontainer);
  #editorStore = new EditorStore(this.#filesStore);
  #terminalStore = new TerminalStore(webcontainer);

  artifacts: Artifacts = import.meta.hot?.data.artifacts ?? map({});

  showWorkbench: WritableAtom<boolean> = import.meta.hot?.data.showWorkbench ?? atom(false);
  currentView: WritableAtom<WorkbenchViewType> = import.meta.hot?.data.currentView ?? atom('code');
  unsavedFiles: WritableAtom<Set<string>> = import.meta.hot?.data.unsavedFiles ?? atom(new Set<string>());
  modifiedFiles = new Set<string>();
  artifactIdList: string[] = [];

  constructor() {
    if (import.meta.hot) {
      import.meta.hot.data.artifacts = this.artifacts;
      import.meta.hot.data.unsavedFiles = this.unsavedFiles;
      import.meta.hot.data.showWorkbench = this.showWorkbench;
      import.meta.hot.data.currentView = this.currentView;
    }
  }

  get previews() {
    return this.#previewsStore.previews;
  }

  get files() {
    return this.#filesStore.files;
  }

  get currentDocument(): ReadableAtom<EditorDocument | undefined> {
    return this.#editorStore.currentDocument;
  }

  get selectedFile(): ReadableAtom<string | undefined> {
    return this.#editorStore.selectedFile;
  }

get firstArtifact(): ArtifactState | undefined {
  if (this.artifactIdList.length === 0) {
    return undefined;
  }
  if (this.artifactIdList.length > 1) {
    console.warn('Multiple artifacts found, returning the first one.');
  }
  return this.#getArtifact(this.artifactIdList[0]);
}

  get filesCount(): number {
    return this.#filesStore.filesCount;
  }

  get showTerminal() {
    return this.#terminalStore.showTerminal;
  }

  toggleTerminal(value?: boolean) {
    this.#terminalStore.toggleTerminal(value);
  }

  attachTerminal(terminal: ITerminal) {
    this.#terminalStore.attachTerminal(terminal);
  }

  onTerminalResize(cols: number, rows: number) {
    this.#terminalStore.onTerminalResize(cols, rows);
  }

  setDocuments(files: FileMap) {
    this.#editorStore.setDocuments(files);

    if (this.#filesStore.filesCount > 0 && this.currentDocument.get() === undefined) {
      // we find the first file and select it
      for (const [filePath, dirent] of Object.entries(files)) {
        if (dirent?.type === 'file') {
          this.setSelectedFile(filePath);
          break;
        }
      }
    }
  }

  setShowWorkbench(show: boolean) {
    this.showWorkbench.set(show);
  }

  setCurrentDocumentContent(newContent: string) {
    const filePath = this.currentDocument.get()?.filePath;

    if (!filePath) {
      return;
    }

    const originalContent = this.#filesStore.getFile(filePath)?.content;
    const unsavedChanges = originalContent !== undefined && originalContent !== newContent;

    this.#editorStore.updateFile(filePath, newContent);

    const currentDocument = this.currentDocument.get();

    if (currentDocument) {
      const previousUnsavedFiles = this.unsavedFiles.get();

      if (unsavedChanges && previousUnsavedFiles.has(currentDocument.filePath)) {
        return;
      }

      const newUnsavedFiles = new Set(previousUnsavedFiles);

      if (unsavedChanges) {
        newUnsavedFiles.add(currentDocument.filePath);
      } else {
        newUnsavedFiles.delete(currentDocument.filePath);
      }

      this.unsavedFiles.set(newUnsavedFiles);
    }
  }

  setCurrentDocumentScrollPosition(position: ScrollPosition) {
    const editorDocument = this.currentDocument.get();

    if (!editorDocument) {
      return;
    }

    const { filePath } = editorDocument;

    this.#editorStore.updateScrollPosition(filePath, position);
  }

  setSelectedFile(filePath: string | undefined) {
    this.#editorStore.setSelectedFile(filePath);
  }

  async saveFile(filePath: string) {
    const documents = this.#editorStore.documents.get();
    const document = documents[filePath];

    if (document === undefined) {
      return;
    }

    await this.#filesStore.saveFile(filePath, document.value);

    const newUnsavedFiles = new Set(this.unsavedFiles.get());
    newUnsavedFiles.delete(filePath);

    this.unsavedFiles.set(newUnsavedFiles);
  }

  async saveCurrentDocument() {
    const currentDocument = this.currentDocument.get();

    if (currentDocument === undefined) {
      return;
    }

    await this.saveFile(currentDocument.filePath);
  }

  resetCurrentDocument() {
    const currentDocument = this.currentDocument.get();

    if (currentDocument === undefined) {
      return;
    }

    const { filePath } = currentDocument;
    const file = this.#filesStore.getFile(filePath);

    if (!file) {
      return;
    }

    this.setCurrentDocumentContent(file.content);
  }

  async saveAllFiles() {
    for (const filePath of this.unsavedFiles.get()) {
      await this.saveFile(filePath);
    }
  }

  getFileModifcations() {
    return this.#filesStore.getFileModifications();
  }

  resetAllFileModifications() {
    this.#filesStore.resetFileModifications();
  }

  abortAllActions() {
    // TODO: what do we wanna do and how do we wanna recover from this?
  }

addArtifact({ messageId, title, id }: ArtifactCallbackData) {
  const artifact = this.#getArtifact(messageId);

  if (artifact) {
    return;
  }

  if (!this.artifactIdList.includes(messageId)) {
    this.artifactIdList.push(messageId);
  }

  this.artifacts.setKey(messageId, {
    id,
    title,
    closed: false,
    runner: new ActionRunner(webcontainer),
  });

  // Send files when first artifact is added
  if (this.artifactIdList.length === 1) {
    this.sendFilesToBackend(id, messageId).catch((error) => {
      console.error('Failed to send files for new artifact:', error);
    });
  }
}

  updateArtifact({ messageId }: ArtifactCallbackData, state: Partial<ArtifactUpdateState>) {
    const artifact = this.#getArtifact(messageId);

    if (!artifact) {
      return;
    }

    this.artifacts.setKey(messageId, { ...artifact, ...state });
  }

  async addAction(data: ActionCallbackData) {
    const { messageId } = data;

    const artifact = this.#getArtifact(messageId);

    if (!artifact) {
      unreachable('Artifact not found');
    }

    artifact.runner.addAction(data);
  }

  async runAction(data: ActionCallbackData) {
    const { messageId } = data;

    const artifact = this.#getArtifact(messageId);

    if (!artifact) {
      unreachable('Artifact not found');
    }

    artifact.runner.runAction(data);
  }

  #getArtifact(id: string) {
    const artifacts = this.artifacts.get();
    return artifacts[id];
  }
async sendFilesToBackend(artifactId: string, messageId?: string) {
  try {
    // Save all files first
    await this.saveAllFiles();
    
    // Wait for files to be available
    let attempts = 0;
    const maxAttempts = 10;
    
    while (this.#filesStore.filesCount === 0 && attempts < maxAttempts) {
      console.log(`Waiting for files... attempt ${attempts + 1}/${maxAttempts}`);
      await new Promise(resolve => setTimeout(resolve, 1000));
      attempts++;
    }
    
    if (this.#filesStore.filesCount === 0) {
      console.log('No files found after waiting, sending empty array');
    }
    
    // Get ALL files from the files store
    const fileMap = this.#filesStore.files.get();
    
    // Debug logging
    console.log('Raw fileMap:', fileMap);
    console.log('FileMap entries count:', Object.keys(fileMap).length);
    console.log('Files store count:', this.#filesStore.filesCount);
    
    // List all entries
    Object.entries(fileMap).forEach(([path, dirent]) => {
      console.log(`Path: ${path}, Type: ${dirent?.type}, Content length: ${dirent?.type === 'file' ? dirent.content?.length : 'N/A'}`);
    });
    
    // Convert FileMap to array format for backend
    const filesArray: Array<{path: string; content: string; is_binary: boolean; size: number}> = [];

    for (const [filePath, dirent] of Object.entries(fileMap)) {
      if (dirent && dirent.type === 'file') {
        filesArray.push({
          path: filePath,
          content: dirent.content,
          is_binary: dirent.isBinary,
          size: dirent.content.length,
        });
      }
    }

    console.log(`Final files array length: ${filesArray.length}`);
    // Get chat history and URL ID
    let chatHistory: any[] = [];
    let urlId: string | undefined;
    let chatIdValue: string | undefined;
    
    try {
      const currentChatId = chatId.get();
      chatIdValue = currentChatId;
      
      if (db && currentChatId) {
        const storedChat = await getMessages(db, currentChatId);
        if (storedChat && storedChat.messages) {
          chatHistory = storedChat.messages;
          urlId = storedChat.urlId; // This might be the URL identifier
        }
      }
    } catch (error) {
      console.error('Failed to get chat history:', error);
    }

    console.log(`Sending ${filesArray.length} files to backend`);

    // Send to backend
    const response = await fetch('/api/files', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        artifact_id: artifactId,
        message_id: messageId,
        chat_id: chatIdValue, // Internal chat ID
        url_id: urlId, // URL identifier
        application_name: this.firstArtifact?.title, // Use artifact title as app name
        files: filesArray,
        messages: chatHistory,
        thread_id: crypto.randomUUID(),
        file_count: filesArray.length,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to send files: ${response.status} - ${errorText}`);
    }

    const result = await response.json();
    console.log('Files sent successfully:', result);
    
    return result;
  } catch (error) {
    console.error('Failed to send files to backend:', error);
    throw error;
  }
}

}

export const workbenchStore = new WorkbenchStore();
