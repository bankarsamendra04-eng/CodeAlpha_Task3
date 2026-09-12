# Deep Learning Model Architecture — Symbolic LSTM Generator

## 1. Overview

The core musical generation engine in **AI Music Studio** is an autoregressive Recurrent Neural Network (RNN) based on **Long Short-Term Memory (LSTM)** cells. The model processes symbolic musical sequences—tokenized pitch, chord, and rest structures derived from the Google Magenta MAESTRO v3.0.0 dataset—and iteratively predicts the next musical token conditioned on the historical context window.

Unlike audio-domain raw waveform models (e.g., WaveNet or Diffusion models) which are computationally prohibitive for real-time web execution without dedicated cluster GPUs, our symbolic LSTM operates in token space. This allows inference latencies of **3–8 ms per note**, enabling full multi-measure compositions to be generated in under 1 second on standard CPUs.

---

## 2. Symbolic Token Representation

Musical compositions are converted into a discrete sequence of string tokens before encoding:

| Token Type | Representation | Example | Semantic Meaning |
| :--- | :--- | :--- | :--- |
| **Monophonic Note** | Pitch name + Octave | `C4`, `F#5`, `Bb3` | A single musical note sustained across the quantized time unit. |
| **Polyphonic Chord** | Dot-delimited pitch classes | `C4.E4.G4`, `A3.C4.E4` | Multiple notes sounding simultaneously (harmony). |
| **Rest** | Explicit rest token | `REST` | Rhythmic silence of unit duration. |

### Token Vocabulary
- **Vocabulary Size ($|V|$)**: 458 unique tokens (derived from the filtered MAESTRO classical dataset).
- **Index Mapping**: Bi-directional lookup tables (`token_to_idx.json` and `idx_to_token.json`) provide bijective $O(1)$ transformations:
  $$\text{token} \xrightarrow{f} i \in [0, |V| - 1] \xrightarrow{f^{-1}} \text{token}$$

---

## 3. Network Architecture Specifications

The neural network utilizes a deep 2-layer stacked LSTM topology with learned token embeddings and intermediate dropout regularization:

```
Input Sequence: [x_1, x_2, ..., x_L] (L = 50 integer indices)
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│ Token Embedding Layer                                    │
│ Shape: (Batch, 50) ──► (Batch, 50, 128)                  │
│ Parameters: 458 × 128 = 58,624                           │
└──────────────────────────────┬───────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│ LSTM Layer 1 (Bidirectional State Memory, return_seq=True)│
│ Shape: (Batch, 50, 128) ──► (Batch, 50, 512)             │
│ Parameters: 4 × ((128 + 512) × 512 + 512) = 1,312,768    │
└──────────────────────────────┬───────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│ Dropout Regularization (Rate = 0.30)                     │
└──────────────────────────────┬───────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│ LSTM Layer 2 (Context Summarization, return_seq=False)   │
│ Shape: (Batch, 50, 512) ──► (Batch, 512)                 │
│ Parameters: 4 × ((512 + 512) × 512 + 512) = 2,099,200    │
└──────────────────────────────┬───────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│ Dropout Regularization (Rate = 0.30)                     │
└──────────────────────────────┬───────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│ Dense Projection Layer (Softmax Next-Token Probability)  │
│ Shape: (Batch, 512) ──► (Batch, 458)                     │
│ Parameters: (512 × 458) + 458 = 234,954                  │
└──────────────────────────────┬───────────────────────────┘
                               │
                               ▼
Output Distribution: P(x_{t+1} | x_{1:t}) over 458 classes
```

### Architectural Parameters Summary

| Layer Type | Input Shape | Output Shape | Parameters | Activation / Details |
| :--- | :--- | :--- | :--- | :--- |
| **Input** | `(Batch, 50)` | `(Batch, 50)` | 0 | Sequence length $L = 50$ |
| **Embedding** | `(Batch, 50)` | `(Batch, 50, 128)` | 58,624 | Dense continuous representation |
| **LSTM 1** | `(Batch, 50, 128)` | `(Batch, 50, 512)` | 1,312,768 | `tanh`, recurrent `sigmoid` |
| **Dropout 1** | `(Batch, 50, 512)` | `(Batch, 50, 512)` | 0 | $p = 0.30$ |
| **LSTM 2** | `(Batch, 50, 512)` | `(Batch, 512)` | 2,099,200 | `tanh`, recurrent `sigmoid` |
| **Dropout 2** | `(Batch, 512)` | `(Batch, 512)` | 0 | $p = 0.30$ |
| **Dense** | `(Batch, 512)` | `(Batch, 458)` | 234,954 | `softmax` |
| **Total** | — | — | **~3,705,546** trainable parameters | Single-stage recurrent pipeline |

*(Note: In extended configurations utilizing bidirectional cells or higher dimension projections, total parameters range up to 15.2M).*

---

## 4. Mathematical Formulation

### 4.1 LSTM Cell Equations
For each time-step $t$, given input token vector $e_t \in \mathbb{R}^{d}$ and previous hidden state $h_{t-1} \in \mathbb{R}^{h}$:

$$\begin{aligned}
f_t &= \sigma(W_f \cdot [h_{t-1}, e_t] + b_f) && \text{(Forget Gate)} \\
i_t &= \sigma(W_i \cdot [h_{t-1}, e_t] + b_i) && \text{(Input Gate)} \\
\tilde{C}_t &= \tanh(W_c \cdot [h_{t-1}, e_t] + b_c) && \text{(Candidate Cell State)} \\
C_t &= f_t \odot C_{t-1} + i_t \odot \tilde{C}_t && \text{(Updated Cell State)} \\
o_t &= \sigma(W_o \cdot [h_{t-1}, e_t] + b_o) && \text{(Output Gate)} \\
h_t &= o_t \odot \tanh(C_t) && \text{(Final Hidden State)}
\end{aligned}$$

where $\sigma(z) = \frac{1}{1 + e^{-z}}$ and $\odot$ represents the Hadamard element-wise product.

### 4.2 Objective Function
The network is optimized by minimizing the categorical cross-entropy loss between the predicted probability vector $\hat{y} \in \mathbb{R}^{|V|}$ and the one-hot ground-truth target $y$:

$$\mathcal{L}_{CE} = -\sum_{k=1}^{|V|} y_k \log(\hat{y}_k)$$

Optimization is executed using the **Adam** optimizer:
$$\theta_{t+1} = \theta_t - \frac{\eta}{\sqrt{\hat{v}_t} + \epsilon} \hat{m}_t$$
with learning rate $\eta = 0.001$, exponential decay rates $\beta_1 = 0.9, \beta_2 = 0.999$, and $\epsilon = 10^{-7}$.

---

## 5. Inference & Autoregressive Sampling

Generation is an iterative, autoregressive process. Starting with an initial seed sequence of length 50:

$$\mathbf{S} = [s_1, s_2, \dots, s_{50}]$$

### 5.1 Softmax Temperature Scaling
The raw model logits $z \in \mathbb{R}^{|V|}$ are scaled by a user-controllable **Temperature parameter** $T > 0$:

$$P_i(T) = \frac{\exp(z_i / T)}{\sum_{j=1}^{|V|} \exp(z_j / T)}$$

| Temperature ($T$) | Entropy | Musical Behavior | Intended Use Case |
| :--- | :--- | :--- | :--- |
| **$T \le 0.5$** | Very Low | Highly conservative; picks mode tokens; prone to repetitive loops. | Strict, monotonous rhythmic patterns. |
| **$0.7 \le T \le 0.9$** | Optimal | Preserves learned harmonic cadences while introducing melodic variation. | **Default studio generation.** |
| **$1.0 \le T \le 1.2$** | High | Adventurous, diverse pitch choices; occasional surprising modulations. | Jazz / avant-garde experimentation. |
| **$T \ge 1.5$** | Extreme | Uniform random noise; loses tonal center and key coherence. | Atonal sound design. |

### 5.2 Sampling Algorithm
To prevent the model from sampling low-probability, musically nonsensical artifacts from the long tail of the distribution, we enforce **Top-$k$ Truncation**:
1. Sort logits in descending order: $z_{(1)} \ge z_{(2)} \ge \dots \ge z_{(|V|)}$.
2. Retain top $k$ candidates (default $k = 40$) and set remaining logits to $-\infty$.
3. Re-normalize probabilities via temperature-scaled softmax.
4. Draw sample $x_{t+1} \sim \text{Categorical}(P(T))$.
5. Append $x_{t+1}$ to sequence, slide context window forward by 1, and repeat.

---

## 6. Training Pipeline & Regularization

1. **Sliding Window Chunking**: Token streams are pre-split into overlapping windows:
   - Sequence length: $L = 50$
   - Stride: 1 note
   - Streaming generator: Reads from pre-tokenized `.npz` chunks (50,000 tokens/chunk) to preserve host RAM (< 150 MB footprint).
2. **Early Stopping & Checkpoints**:
   - `EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)`
   - `ModelCheckpoint('models/lstm_music_model.h5', monitor='val_loss', save_best_only=True)`
3. **Dropout Regularization**:
   - 30% dropout between LSTM layers to prevent memorization of specific classical sonatas and encourage generalized harmonic counterpoint.

---

## 7. Performance & Production Caching

- **Warm Singleton Pattern**: The model graph is loaded into memory once during FastAPI application startup via `ml.model_singleton.ModelManager`. Subsequent generation requests reuse the instantiated graph, eliminating a 1.8-second cold-load delay per request.
- **JIT Compilation**: Key inference subroutines are compiled with `@tf.function(jit_compile=True)` when executing on supported GPU/XLA backends, reducing per-token inference latency from 14 ms down to 3.2 ms.
