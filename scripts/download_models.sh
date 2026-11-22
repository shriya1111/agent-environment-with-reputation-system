mkdir -p ${MODELS_DIR:-$HOME/models}
set -e
cd ${MODELS_DIR:-$HOME/models}
dl(){ [ -s "$2" ] || curl -sL --retry 4 -o "$2" "https://huggingface.co/$1/resolve/main/$3"; echo "done $2 $(du -h $2|cut -f1)"; }
dl Qwen/Qwen2.5-3B-Instruct-GGUF qwen2.5-3b.gguf qwen2.5-3b-instruct-q4_k_m.gguf
dl bartowski/Llama-3.2-3B-Instruct-GGUF llama3.2-3b.gguf Llama-3.2-3B-Instruct-Q4_K_M.gguf
dl LiquidAI/LFM2-2.6B-GGUF lfm2-2.6b.gguf LFM2-2.6B-Q4_K_M.gguf
dl ibm-granite/granite-4.0-h-micro-GGUF granite4-h-micro.gguf granite-4.0-h-micro-Q4_K_M.gguf
dl mradermacher/Qwen2.5-3B-Instruct-abliterated-GGUF qwen2.5-3b-abliterated.gguf Qwen2.5-3B-Instruct-abliterated.Q4_K_M.gguf
