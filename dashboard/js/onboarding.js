/**
 * Onboarding Wizard JavaScript
 * Handles step navigation, API calls, and state management
 */

class OnboardingWizard {
  constructor() {
    this.currentStep = 1;
    this.totalSteps = 4;
    this.formData = {
      organization_type: null,
      department_choice: null
    };
    this.loading = false;
    this.token = this.getAuthToken();

    this.initElements();
    this.setupEventListeners();
    this.loadInitialState();
  }

  /**
   * Initialize DOM elements
   */
  initElements() {
    this.wizardContainer = document.querySelector('.wizard-container');
    this.progressFill = document.querySelector('.progress-fill');
    this.progressLabel = document.querySelector('.progress-label');
    this.panels = Array.from(document.querySelectorAll('.wizard-panel'));
    this.nextBtn = document.getElementById('btn-next');
    this.backBtn = document.getElementById('btn-back');
    this.skipBtn = document.getElementById('btn-skip');
    this.errorMessage = document.querySelector('.error-message');
    this.successMessage = document.querySelector('.success-message');
  }

  /**
   * Setup event listeners
   */
  setupEventListeners() {
    if (this.nextBtn) {
      this.nextBtn.addEventListener('click', () => this.handleNext());
    }
    if (this.backBtn) {
      this.backBtn.addEventListener('click', () => this.handleBack());
    }
    if (this.skipBtn) {
      this.skipBtn.addEventListener('click', () => this.handleSkip());
    }

    // Form input change listeners
    document.querySelectorAll('input[type="radio"]').forEach(input => {
      input.addEventListener('change', (e) => this.handleFormChange(e));
    });

    // Handle keyboard navigation
    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight') this.handleNext();
      if (e.key === 'ArrowLeft') this.handleBack();
      if (e.key === 'Escape') this.handleSkip();
    });
  }

  /**
   * Load initial state from API and localStorage
   */
  async loadInitialState() {
    try {
      // First, check localStorage for cached state
      const cachedState = this.getLocalStorageState();
      if (cachedState) {
        this.currentStep = cachedState.currentStep || 1;
        this.formData = cachedState.formData || {};
        console.log('Loaded state from localStorage:', { currentStep: this.currentStep, formData: this.formData });
      }

      // Then, fetch fresh state from API
      await this.fetchStatus();
    } catch (error) {
      console.error('Error loading initial state:', error);
      this.showError('オンボーディング状態の読み込みに失敗しました');
    }
  }

  /**
   * Fetch onboarding status from API
   */
  async fetchStatus() {
    try {
      const response = await fetch('/api/onboarding/status', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('認証が失われています。ログインしてください。');
        }
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      console.log('Fetched status:', data);

      // Update state from API
      this.currentStep = data.current_step || 1;
      if (data.organization_type) {
        this.formData.organization_type = data.organization_type;
      }
      if (data.department_choice) {
        this.formData.department_choice = data.department_choice;
      }

      // If already completed, redirect
      if (data.onboarding_completed) {
        this.handleCompletion();
        return;
      }

      // Update UI
      this.updateUI();
      this.saveLocalStorageState();
    } catch (error) {
      console.error('Error fetching status:', error);
      throw error;
    }
  }

  /**
   * Handle form input change
   */
  handleFormChange(event) {
    const { name, value } = event.target;
    this.formData[name] = value;
    console.log('Form data updated:', this.formData);
    this.saveLocalStorageState();
  }

  /**
   * Validate current step's form data
   */
  validateStep() {
    switch (this.currentStep) {
      case 1:
        // Welcome screen - no validation needed
        return true;
      case 2:
        // Organization type selection required
        if (!this.formData.organization_type) {
          this.showError('組織タイプを選択してください');
          return false;
        }
        return true;
      case 3:
        // Department choice required
        if (!this.formData.department_choice) {
          this.showError('部署を選択してください');
          return false;
        }
        return true;
      case 4:
        // Confirmation - no validation needed
        return true;
      default:
        return true;
    }
  }

  /**
   * Handle next button click
   */
  async handleNext() {
    if (this.loading) return;

    // Validate current step
    if (!this.validateStep()) {
      return;
    }

    try {
      this.loading = true;
      this.setButtonsDisabled(true);

      // Save current step data to API
      if (this.currentStep < this.totalSteps) {
        await this.updateStep();
      }

      // Move to next step
      if (this.currentStep === this.totalSteps) {
        // Complete onboarding
        await this.completeOnboarding();
      } else {
        this.currentStep++;
        this.updateUI();
        this.saveLocalStorageState();
      }
    } catch (error) {
      console.error('Error in handleNext:', error);
      this.showError('ステップの更新に失敗しました: ' + error.message);
    } finally {
      this.loading = false;
      this.setButtonsDisabled(false);
    }
  }

  /**
   * Handle back button click
   */
  handleBack() {
    if (this.currentStep > 1) {
      this.currentStep--;
      this.updateUI();
      this.saveLocalStorageState();
    }
  }

  /**
   * Handle skip button click
   */
  async handleSkip() {
    const confirmed = confirm('オンボーディングをスキップしますか？この後いつでも実行できます。');
    if (!confirmed) return;

    try {
      this.loading = true;
      this.setButtonsDisabled(true);

      const response = await fetch('/api/onboarding/skip', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to skip onboarding: ${response.status}`);
      }

      this.showSuccess('オンボーディングをスキップしました');
      this.clearLocalStorageState();
      setTimeout(() => {
        window.location.href = '/dashboard';
      }, 1000);
    } catch (error) {
      console.error('Error skipping onboarding:', error);
      this.showError('スキップに失敗しました: ' + error.message);
    } finally {
      this.loading = false;
      this.setButtonsDisabled(false);
    }
  }

  /**
   * Update step via API
   */
  async updateStep() {
    const payload = {
      current_step: this.currentStep,
      organization_type: this.formData.organization_type,
      department_choice: this.formData.department_choice
    };

    const response = await fetch('/api/onboarding/step', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Failed to update step: ${response.status}`);
    }

    const data = await response.json();
    console.log('Step updated:', data);
    return data;
  }

  /**
   * Complete onboarding
   */
  async completeOnboarding() {
    const response = await fetch('/api/onboarding/complete', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to complete onboarding: ${response.status}`);
    }

    const data = await response.json();
    console.log('Onboarding completed:', data);
    this.handleCompletion();
  }

  /**
   * Handle completion
   */
  handleCompletion() {
    this.clearLocalStorageState();
    this.showSuccess('オンボーディングが完了しました！');
    setTimeout(() => {
      window.location.href = '/dashboard';
    }, 1500);
  }

  /**
   * Update UI based on current step
   */
  updateUI() {
    this.hideAllPanels();
    this.showPanel(this.currentStep);
    this.updateProgressBar();
    this.updateButtons();
    this.restoreFormData();
  }

  /**
   * Hide all panels
   */
  hideAllPanels() {
    this.panels.forEach(panel => {
      panel.classList.remove('active', 'exit-left');
    });
  }

  /**
   * Show specific panel
   */
  showPanel(step) {
    const panel = document.getElementById(`step-${step}`);
    if (panel) {
      panel.classList.add('active');
    }
  }

  /**
   * Update progress bar and label
   */
  updateProgressBar() {
    const progress = (this.currentStep / this.totalSteps) * 100;
    if (this.progressFill) {
      this.progressFill.style.width = `${progress}%`;
    }
    if (this.progressLabel) {
      this.progressLabel.textContent = `ステップ ${this.currentStep} / ${this.totalSteps}`;
    }
  }

  /**
   * Update button states
   */
  updateButtons() {
    // Back button
    if (this.backBtn) {
      this.backBtn.style.display = this.currentStep > 1 ? 'block' : 'none';
    }

    // Next/Complete button
    if (this.nextBtn) {
      if (this.currentStep === this.totalSteps) {
        this.nextBtn.textContent = 'オンボーディングを完了';
      } else {
        this.nextBtn.textContent = '次へ';
      }
    }

    // Skip button
    if (this.skipBtn) {
      this.skipBtn.style.display = this.currentStep < this.totalSteps ? 'block' : 'none';
    }
  }

  /**
   * Restore form data from current state
   */
  restoreFormData() {
    // Check organization type radios
    if (this.formData.organization_type) {
      const orgRadio = document.querySelector(
        `input[name="organization_type"][value="${this.formData.organization_type}"]`
      );
      if (orgRadio) {
        orgRadio.checked = true;
      }
    }

    // Check department choice radios
    if (this.formData.department_choice) {
      const deptRadio = document.querySelector(
        `input[name="department_choice"][value="${this.formData.department_choice}"]`
      );
      if (deptRadio) {
        deptRadio.checked = true;
      }
    }
  }

  /**
   * Set buttons disabled state
   */
  setButtonsDisabled(disabled) {
    [this.nextBtn, this.backBtn, this.skipBtn].forEach(btn => {
      if (btn) {
        btn.disabled = disabled;
        if (disabled) {
          btn.classList.add('loading');
        } else {
          btn.classList.remove('loading');
        }
      }
    });
  }

  /**
   * Show error message
   */
  showError(message) {
    if (this.errorMessage) {
      this.errorMessage.textContent = message;
      this.errorMessage.classList.add('show');
      setTimeout(() => {
        this.errorMessage.classList.remove('show');
      }, 5000);
    }
  }

  /**
   * Show success message
   */
  showSuccess(message) {
    if (this.successMessage) {
      this.successMessage.textContent = message;
      this.successMessage.classList.add('show');
      setTimeout(() => {
        this.successMessage.classList.remove('show');
      }, 5000);
    }
  }

  /**
   * Get authentication token
   */
  getAuthToken() {
    // Try to get token from localStorage
    const token = localStorage.getItem('auth_token');
    if (token) return token;

    // Try to get from cookie
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      const [name, value] = cookie.trim().split('=');
      if (name === 'auth_token' || name === 'access_token') {
        return decodeURIComponent(value);
      }
    }

    return '';
  }

  /**
   * Save state to localStorage
   */
  saveLocalStorageState() {
    const state = {
      currentStep: this.currentStep,
      formData: this.formData,
      timestamp: new Date().toISOString()
    };
    localStorage.setItem('onboarding_state', JSON.stringify(state));
    console.log('State saved to localStorage:', state);
  }

  /**
   * Get state from localStorage
   */
  getLocalStorageState() {
    const stored = localStorage.getItem('onboarding_state');
    if (!stored) return null;

    try {
      const state = JSON.parse(stored);
      // Consider state valid if less than 24 hours old
      const timestamp = new Date(state.timestamp);
      const now = new Date();
      const hours = (now - timestamp) / (1000 * 60 * 60);

      if (hours < 24) {
        return state;
      }
    } catch (error) {
      console.error('Error parsing localStorage state:', error);
    }

    return null;
  }

  /**
   * Clear state from localStorage
   */
  clearLocalStorageState() {
    localStorage.removeItem('onboarding_state');
    console.log('State cleared from localStorage');
  }
}

/**
 * Initialize wizard when DOM is ready
 */
document.addEventListener('DOMContentLoaded', () => {
  console.log('Initializing OnboardingWizard...');
  window.wizard = new OnboardingWizard();
});
