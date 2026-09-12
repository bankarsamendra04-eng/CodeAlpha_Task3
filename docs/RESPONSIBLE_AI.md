# Responsible AI and Dataset Provenance

## 1. Overview & Ethical Principles

**AI Music Studio** is an assistive generative artificial intelligence system developed to support human musical creativity, composition experimentation, and algorithmic research. We believe generative AI should empower musicians and creators rather than deceive audiences, infringe upon artistic rights, or misrepresent machine-generated artifacts.

This document defines our ethical framework, dataset lineage, technological limitations, copyright considerations, and mandatory terms of responsible use.

---

## 2. Dataset Provenance & Attribution

AI Music Studio's symbolic neural network was trained on the **MAESTRO (MIDI and Audio Edited for Synchronous Tracks and Organization) Dataset v3.0.0**.

### Dataset Specifications
- **Source**: The MAESTRO dataset is a collaborative project created by the **Magenta team at Google** in partnership with the **Concert Artists Guild** and the **Minnesota International Piano-e-Competition**.
- **Content**: Comprises approximately 200 hours of virtuoso classical piano performances captured via Yamaha Disklavier reproducing pianos from live competitive recital rounds.
- **Data Modality Used**: AI Music Studio extracts and trains exclusively on the **symbolic MIDI performances**, consisting of note-on, note-off, quantized pitch tokens, chord groupings, and timing durations.
- **License**: The MAESTRO dataset is licensed under the **Creative Commons Attribution 4.0 International (CC BY 4.0)** license.
  - *Attribution*: Hawthorne, et al., *"Enabling Factorized Piano Music Modeling and Generation with the MAESTRO Dataset"*, International Conference on Learning Representations (ICLR), 2019.
- **Data Integrity**: Training data has been validated, split into canonical Train (80%), Validation (10%), and Test (10%) partitions, and audited for zero synthetic or corrupted MIDI sequences.

---

## 3. Dataset Licensing & Intellectual Property Compliance

- **Public Domain Repertoire**: The underlying musical compositions performed in the MAESTRO dataset are classical masterworks primarily in the **public domain** (e.g., compositions by J.S. Bach, L.v. Beethoven, F. Chopin, W.A. Mozart, J. Brahms, F. Liszt).
- **Training Rights**: Training machine learning models on publicly available, permissively licensed symbolic data complies with fair training standards and research use under CC BY 4.0.
- **No Private Scrapes**: AI Music Studio does not scrape commercial music streaming services, private proprietary music libraries, or copyrighted modern sound recordings.

---

## 4. Model Architecture & Operational Limitations

Understanding what the model can and cannot do is essential for responsible deployment:

### Architectural Scope
- **Symbolic Sequence Modeling**: The generative core is a 2-layer Long Short-Term Memory (LSTM) recurrent neural network that predicts discrete musical tokens (notes, chords, rests, and durations) sequentially.
- **Prompt Interpretation**: Groq / Llama-3 models translate natural-language user descriptions into structured parametric constraints (tempo, mood, key, scale, complexity). Groq does not author the musical notes; it only steers parameter boundaries.

### Technical Limitations
1. **Classical Piano Bias**: Because the primary training corpus is the MAESTRO dataset, the model exhibits strong harmonic and stylistic tendencies toward classical polyphonic piano textures.
2. **Context Window Limitations**: As an LSTM model operating over bounded token contexts (e.g. 50-token history), the generator cannot maintain long-range sonata-allegro structural forms or symphonic thematic developments over extended durations (exceeding 3–5 minutes).
3. **No Vocal or Lyric Synthesis**: The system strictly produces symbolic note events and synthesized MIDI/WAV audio. It cannot synthesize human vocals, speech, or lyrics.
4. **Occasional Repetition or Dissonance**: Like all probabilistic language and sequence models, sampling at high temperatures ($> 1.2$) may produce tonal dissonance, while sampling at very low temperatures ($< 0.4$) may cause harmonic looping or repetitive motifs.

---

## 5. Mandatory AI-Generated Music Disclosure Policy

Transparency is mandatory when publishing or distributing works generated in whole or in part by AI Music Studio:

1. **Clear Labeling**: Any public distribution, performance, or broadcast of audio derived from this application should clearly disclose that the underlying composition or arrangement was generated using artificial intelligence.
2. **Recommended Disclosure Statement**:
   > *"This musical piece was generated in whole or in part using AI Music Studio, an artificial intelligence generative music system based on an LSTM neural network."*
3. **No Deception**: Users must not present AI Music Studio outputs as purely unassisted human acoustic performances or spontaneous human improvisation.

---

## 6. Strict Policy: No Artist Impersonation & No False Attribution

To protect musical artists, their livelihoods, and their reputations, the following conduct is strictly prohibited:

- **No Impersonation**: Users may not attempt to impersonate living musical artists, performers, composers, or ensembles.
- **No False Endorsement**: Users may not market or brand generated music with phrases claiming or implying an official collaboration, tribute, or endorsement by real artists (e.g., claiming a track is *"the unreleased single by Artist X"*).
- **No Deceptive Attribution**: You may not affix another creator's name, trademark, or likeness to works generated by this software.

---

## 7. Copyright Considerations & Intellectual Property Status

### No Automatic "Copyright-Free" Guarantee
- **Important Notice**: AI Music Studio makes **no claim and gives no warranty that all generated music is automatically copyright-free, public domain, or immune from third-party infringement claims**.
- **Probabilistic Overlap**: While the model predicts novel note sequences based on statistical distributions, generative models may occasionally generate melodies, intervals, or chord progressions that bear coincidental resemblance to existing copyrighted works.
- **No Claim of Legal Ownership**: AI Music Studio does not claim legal ownership or copyright over the outputs generated by users, nor does it guarantee that the user acquires registrable copyright under various international legal jurisdictions.

### Jurisdictional Nuance
- In many legal jurisdictions (including the United States and the European Union), purely machine-generated works lacking substantial human creative expression may not qualify for copyright protection.
- Where a user significantly edits, arranges, performs, or transforms the generated MIDI material into a derivative work, the user is advised to consult qualified legal counsel regarding their jurisdiction's copyright eligibility criteria.

---

## 8. User Responsibility for Generated Content

Users of AI Music Studio bear sole legal and ethical responsibility for:

1. **Independent Verification**: Conducting due diligence (including melody clearance, acoustic similarity comparison, and audio fingerprinting) prior to commercial release or sync licensing.
2. **Third-Party Rights**: Ensuring that any prompt or derived track does not infringe upon the copyrights, trademarks, privacy rights, or moral rights of third parties.
3. **Platform Terms Compliance**: Adhering to the terms of service of streaming distributors, music publishers, content ID systems (e.g. YouTube Content ID), and digital service providers (DSPs) regarding synthetic or AI-assisted content disclosure.

---

## 9. Responsible Commercial Usage Guidelines

If you intend to use compositions created with AI Music Studio in commercial media (such as film scores, video game soundtracks, podcasts, advertisements, or recorded albums):

1. **Treat Output as an Ideation Co-Creator**: We recommend treating generated MIDI files as inspirational starting points, thematic sketches, or harmonic scaffolds to be arranged, re-instrumented, and refined with human musicianship.
2. **Perform Originality Clearance**: Run the generated audio through commercial music recognition and audio fingerprinting tools to check for accidental melodic similarity against existing cataloged compositions.
3. **Transparent Sync Licensing**: Provide full transparency to synchronization clients and publishers regarding the AI-assisted nature of the cue or track.
4. **SoundFont Licensing**: Ensure that any third-party SoundFonts (.sf2) or virtual instrument plugins used for final WAV rendering are licensed for commercial audio distribution.

---

## 10. Regulatory and Certification Disclaimers

- **No Government Approval or Endorsement**: AI Music Studio, its algorithms, and its documentation have **not** been approved, certified, vetted, or endorsed by any governmental agency, department of commerce, patent office, or national standard-setting authority.
- **No Legal Advice**: The information in this document is provided for ethical guidance and policy compliance. It does not constitute formal legal advice. Users requiring legal clarity regarding copyright registration, licensing, or IP liability should seek advice from an attorney specializing in music and intellectual property law.
