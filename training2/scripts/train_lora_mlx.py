"""
Reproducible LoRA Adapter Fine-Tuning Script for Battle Talk (MLX on Apple Silicon / CUDA Transformers).
Fine-tunes Qwen3-4B / Qwen2.5-3B on the Battle Talk dialogue, intent, and morale dataset.
"""
import argparse
import subprocess
import sys
from pathlib import Path


def run_training(
    model_name: str,
    dataset_dir: Path,
    adapter_dir: Path,
    batch_size: int = 2,
    lora_rank: int = 16,
    lora_alpha: int = 32,
    num_iters: int = 600,
    learning_rate: float = 1e-4,
    save_every: int = 200,
    num_layers: int = 16,
    grad_checkpoint: bool = True,
) -> None:
    print("=" * 60)
    print(" Syntax Error 26 — Battle Talk LoRA Fine-Tuning (Model 2)")
    print(f" Base Model      : {model_name}")
    print(f" Dataset Path    : {dataset_dir}")
    print(f" Adapter Output  : {adapter_dir}")
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
    ]

    print(f"Executing: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print("\nLoRA training completed successfully!")
    except FileNotFoundError:
        print("\nNote: mlx_lm is designed for Apple Silicon / target training machine.")
        print("Run this script on the target training environment.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Battle Talk LoRA Adapter")
    parser.add_argument("--model", default="Qwen/Qwen2.5-3B-Instruct", help="Base model name or path")
    parser.add_argument("--iters", type=int, default=600, help="Training iterations")
    parser.add_argument("--batch-size", type=int, default=2, help="Batch size")
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
    )
