// ==================== GLOBAL STATE ====================
export class AppState {
  constructor() {
    this.binders = [];
    this.currentOpenBinderId = null;
    this.isResearchView = false;
    this.currentResearchBinder = null;
    this.isThinking = false;
    this.isGeneratingResponse = false;
    this.isLoadingMore = false;
    this.nextCursor = null;
    this.totalCount = null;
    this.searchParams = null;
    this.currentFilter = "relevance";
    this.lastLLMCall=0;
    this.currentPaperViewPapers = [];   // papers available in paperView
    this.currentPaperViewSelected = null; // the paper currently open
  }
}
