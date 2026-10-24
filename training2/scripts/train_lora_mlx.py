"""
Reproducible LoRA Adapter Fine-Tuning Script for Battle Talk (MLX on Apple Silicon / CUDA Transformers).
Fine-tunes Qwen3-4B / Qwen2.5-3B on the Battle Talk dialogue, intent, and morale dataset.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run_training(
    model_name: str,
    dataset_dir: Path,
    adapter_dir: Path,
    batch_size: int = 4,
    lora_rank: int = 16,
    lora_alpha: int = 32,
    num_iters: int = 600,
    learning_rate: float = 1e-4,
    save_every: int = 200,
    max_seq_length: int = 256,
    val_batches: int = 25,
) -> None:
    print("=" * 60)
    print(" Syntax Error 26 — Battle Talk LoRA Fine-Tuning (Model 2)")
    print(f" Base Model      : {model_name}")
    print(f" Dataset Path    : {dataset_dir}")
    print(f" Adapter Output  : {adapter_dir}")
    print(f" Batch Size      : {batch_size} (Optimized for Apple M5 16GB UMA)")
    print(f" Max Seq Length  : {max_seq_length}")
    print(f" LoRA Config     : Rank={lora_rank}, Alpha={lora_alpha}, LR={learning_rate}")
    print("=" * 60)

    adapter_dir.mkdir(parents=True, exist_ok=True)
    config_dir = dataset_dir.parent.parent / "configs"
    config_path = config_dir / "lora_config.yaml"

    cmd = [
        sys.executable,
        "-m",
        "mlx_lm",
        "lora",
        "--train",
        "--model",
        model_name,
        "--data",
        str(dataset_dir),
        "--adapter-path",
        str(adapter_dir),
        "--config",
        str(config_path),
        "--iters",
        str(num_iters),
        "--batch-size",
        str(batch_size),
        "--learning-rate",
        str(learning_rate),
        "--save-every",
        str(save_every),
        "--steps-per-report",
        "25",
        "--steps-per-eval",
        "100",
        "--val-batches",
        str(val_batches),
        "--max-seq-length",
        str(max_seq_length),
    ]

    # Prepend caffeinate on macOS to prevent App Nap / CPU/GPU throttling
    if sys.platform == "darwin" and shutil.which("caffeinate"):
        cmd = ["caffeinate", "-i"] + cmd

    print(f"Executing: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print("\nLoRA training completed successfully!")
    except FileNotFoundError:
        print("\nNote: mlx_lm is designed for Apple Silicon / target training machine.")
        print("Run this script on the target training environment.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Battle Talk LoRA Adapter")
    parser.add_argument("--model", default="mlx-community/Qwen2.5-3B-Instruct-4bit", help="Base model name or path")
    parser.add_argument("--iters", type=int, default=600, help="Training iterations")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size")
    parser.add_argument("--max-seq-length", type=int, default=256, help="Max sequence length")
    args = parser.parse_args()

    repo_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = repo_dir / "training2" / "data" / "battle_talk"
    out_adapter = repo_dir / "training2" / "adapters" / "battle_talk_adapter"

    run_training(
        model_name=args.model,
        dataset_dir=data_dir,
        adapter_dir=out_adapter,
        batch_size=args.batch_size,
        num_iters=args.iters,
        max_seq_length=args.max_seq_length,
    )
