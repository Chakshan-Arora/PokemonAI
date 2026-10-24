"""
Reproducible LoRA Adapter Fine-Tuning Script using MLX on Apple Silicon (M5).
Supports training Adapter A (Bonding) and Adapter B (Battle) on Qwen3-4B or Qwen3-1.7B.
"""
import argparse
import subprocess
import sys
import yaml
from pathlib import Path


def run_training(
    model_name: str,
    dataset_dir: Path,
    adapter_dir: Path,
    batch_size: int = 2,
    lora_rank: int = 16,
    lora_alpha: int = 32,
    num_iters: int = 500,
    learning_rate: float = 1e-4,
    save_every: int = 200,
    num_layers: int = 16,
    grad_checkpoint: bool = False,
) -> None:
    print("=" * 60)
    print(" Syntax Error 26 — MLX LoRA Fine-Tuning Pipeline")
    print(f" Target Hardware : Apple Silicon (MacBook Air M5, 16 GB UMA)")
    print(f" Base Model      : {model_name}")
    print(f" Dataset Path    : {dataset_dir}")
    print(f" Adapter Output  : {adapter_dir}")
    print(f" LoRA Config     : Rank={lora_rank}, Alpha={lora_alpha}, LR={learning_rate}")
    print("=" * 60)

    adapter_dir.mkdir(parents=True, exist_ok=True)

    # Generate or update YAML configuration for mlx_lm lora
    config_dir = dataset_dir.parent.parent / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"lora_config_r{lora_rank}.yaml"

    # Proper MLX LoRA scaling: alpha / rank (e.g. 32 / 16 = 2.0)
    effective_scale = float(lora_alpha) / float(lora_rank) if lora_rank > 0 else 1.0

    config_data = {
        "fine_tune_type": "lora",
        "num_layers": num_layers,
        "grad_checkpoint": grad_checkpoint,
        "max_seq_length": 512,
        "mask_prompt": True,
        "lora_parameters": {
            "rank": lora_rank,
            "scale": effective_scale,
            "dropout": 0.05,
        },
    }

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, default_flow_style=False)

    # Command using modern mlx_lm CLI syntax: python -m mlx_lm lora ...
    cmd = [
        sys.executable,
        "-m", "mlx_lm", "lora",
        "--model", model_name,
        "--train",
        "--data", str(dataset_dir),
        "--adapter-path", str(adapter_dir),
        "--batch-size", str(batch_size),
        "--iters", str(num_iters),
        "--learning-rate", str(learning_rate),
        "--steps-per-report", "25",
        "--steps-per-eval", "100",
        "--save-every", str(save_every),
        "--max-seq-length", "512",
        "--config", str(config_path),
    ]

    if grad_checkpoint:
        cmd.append("--grad-checkpoint")

    print(f"\nUsing generated configuration: {config_path}")
    print("Executing Command:")
    print(" ".join(cmd))
    print("-" * 60)

    try:
        subprocess.run(cmd, check=True)
        print(f"\n[+] Training completed successfully! Adapter weights saved to: {adapter_dir}")
    except subprocess.CalledProcessError as exc:
        print(f"\n[!] Training process exited with code {exc.returncode}")
        sys.exit(exc.returncode)
    except FileNotFoundError:
        print("\n[!] 'mlx_lm' package is not installed in the active environment.")
        print("Please install requirements using: pip install -r PokemonAI/training/requirements.txt")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Train Pokemon Decision LoRA Adapter using MLX on Apple Silicon")
    parser.add_argument(
        "--adapter-type",
        choices=["bonding", "battle"],
        default="bonding",
        help="Adapter to train: 'bonding' (Adapter A) or 'battle' (Adapter B)",
    )
    
    # Auto-detect local 4-bit converted model if available
    repo_root = Path(__file__).resolve().parent.parent.parent
    local_4bit = repo_root / "models" / "Qwen3-4B-4bit"
    default_model = str(local_4bit) if local_4bit.exists() else "Qwen/Qwen3-4B-Base"

    parser.add_argument(
        "--model",
        default=default_model,
        help=f"Model repository or local directory (default: {default_model})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Per-device batch size (default: 1 for 16 GB Apple Silicon)",
    )
    parser.add_argument(
        "--iters",
        type=int,
        default=500,
        help="Number of training iterations (default: 500)",
    )
    parser.add_argument(
        "--lora-rank",
        type=int,
        default=16,
        help="LoRA rank dimension (default: 16)",
    )
    parser.add_argument(
        "--lora-alpha",
        type=int,
        default=32,
        help="LoRA alpha scaling factor (default: 32)",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=1e-4,
        help="Adam learning rate (default: 0.0001)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Custom output directory for adapter checkpoints",
    )
    parser.add_argument(
        "--grad-checkpoint",
        action="store_true",
        default=True,
        help="Enable gradient checkpointing to conserve memory (default: True)",
    )

    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    dataset_dir = repo_root / "data" / args.adapter_type

    if args.output_dir:
        adapter_dir = Path(args.output_dir)
    else:
        adapter_dir = repo_root / "adapters" / f"{args.adapter_type}_adapter"

    run_training(
        model_name=args.model,
        dataset_dir=dataset_dir,
        adapter_dir=adapter_dir,
        batch_size=args.batch_size,
        lora_rank=args.lora_rank,
        lora_alpha=args.lora_alpha,
        num_iters=args.iters,
        learning_rate=args.learning_rate,
        grad_checkpoint=args.grad_checkpoint,
    )


if __name__ == "__main__":
    main()
