import React from 'react'
import { Server, CheckCircle2, Loader2, RefreshCw, AlertCircle, Info } from 'lucide-react'
import { isEnvSet, getEnvVarName } from './setupUtils'
import styles from '../Setup.module.css'

/**
 * LLM provider and model selection step for the setup wizard.
 *
 * @param {string} llmProvider - Selected provider ('ollama' or 'openai')
 * @param {function} setLlmProvider - Function to update provider
 * @param {Array} ollamaModels - Available Ollama models
 * @param {string} selectedModel - Selected chat model
 * @param {function} setSelectedModel - Function to update chat model
 * @param {string} selectedEmbeddingModel - Selected embedding model
 * @param {function} setSelectedEmbeddingModel - Function to update embedding model
 * @param {boolean} loadingModels - Whether models are being loaded
 * @param {function} loadOllamaModels - Function to refresh model list
 * @param {Object} envOverrides - Environment variable overrides
 */
const StepLlm = ({
  llmProvider,
  setLlmProvider,
  ollamaModels,
  selectedModel,
  setSelectedModel,
  selectedEmbeddingModel,
  setSelectedEmbeddingModel,
  loadingModels,
  loadOllamaModels,
  envOverrides
}) => {
  return (
    <div className={styles.stepContent}>
      <h2>LLM Configuration</h2>
      <p className={styles.stepDescription}>
        Select which AI model provider to use for document analysis.
      </p>

      <div className={styles.providerCards}>
        <div
          className={`${styles.providerCard} ${llmProvider === 'ollama' ? styles.selected : ''}`}
          onClick={() => setLlmProvider('ollama')}
        >
          <Server size={32} />
          <h3>Ollama (Local)</h3>
          <p>Run models locally on your hardware. Private and free.</p>
          {llmProvider === 'ollama' && <CheckCircle2 className={styles.checkmark} />}
        </div>

        <div
          className={`${styles.providerCard} ${llmProvider === 'openai' ? styles.selected : ''} ${styles.disabled}`}
          title="Coming soon"
        >
          <Server size={32} />
          <h3>OpenAI</h3>
          <p>Use GPT-4 and other OpenAI models. Requires API key.</p>
          <span className={styles.comingSoon}>Coming Soon</span>
        </div>
      </div>

      {llmProvider === 'ollama' && (
        <div className={styles.modelSelection}>
          <h3>Select Models</h3>

          {/* Env override notice */}
          {(isEnvSet('ollama.model', envOverrides) || isEnvSet('ollama.embedding_model', envOverrides)) && (
            <div className={styles.infoBox}>
              <Info size={20} />
              <span>
                Some models are pre-configured via environment variables.
                You can change them here or keep the defaults.
              </span>
            </div>
          )}

          {loadingModels ? (
            <div className={styles.loadingState}>
              <Loader2 size={24} className={styles.spinner} />
              <span>Loading available models...</span>
            </div>
          ) : ollamaModels.length > 0 ? (
            <>
              <div className={styles.formGroup}>
                <label>
                  Chat Model
                  {isEnvSet('ollama.model', envOverrides) && (
                    <span className={styles.envBadge} title={`Default from ${getEnvVarName('ollama.model', envOverrides)}`}>
                      ENV
                    </span>
                  )}
                </label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                >
                  {ollamaModels.map(model => (
                    <option key={model.name || model} value={model.name || model}>
                      {model.name || model}
                    </option>
                  ))}
                </select>
                <span className={styles.hint}>Used for generating summaries and tags</span>
              </div>

              <div className={styles.formGroup}>
                <label>
                  Embedding Model
                  {isEnvSet('ollama.embedding_model', envOverrides) && (
                    <span className={styles.envBadge} title={`Default from ${getEnvVarName('ollama.embedding_model', envOverrides)}`}>
                      ENV
                    </span>
                  )}
                </label>
                <select
                  value={selectedEmbeddingModel}
                  onChange={(e) => setSelectedEmbeddingModel(e.target.value)}
                >
                  {ollamaModels.map(model => (
                    <option key={model.name || model} value={model.name || model}>
                      {model.name || model}
                    </option>
                  ))}
                </select>
                <span className={styles.hint}>Used for semantic search (nomic-embed-text recommended)</span>
              </div>
            </>
          ) : (
            <div className={styles.warningBox}>
              <AlertCircle size={20} />
              <div>
                <p>No models found in Ollama.</p>
                <p className={styles.hint}>
                  Pull a model first: <code>ollama pull phi4-mini</code>
                </p>
              </div>
            </div>
          )}

          <button
            className={styles.refreshButton}
            onClick={loadOllamaModels}
            disabled={loadingModels}
          >
            <RefreshCw size={16} />
            Refresh Models
          </button>
        </div>
      )}
    </div>
  )
}

export default StepLlm
