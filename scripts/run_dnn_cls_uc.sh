#!/bin/sh
CUR_DIR=$(cd $(dirname "$0")/..;pwd)
echo "current path: "$CUR_DIR
export PYTHONPATH="${CUR_DIR}":$PYTHONPATH
export DatasetPath="${CUR_DIR}/UC_datasets"

# dnn 训练模型
CUDA_VISIBLE_DEVICES=0 python -u runs/run_dnn_cls.py \
    --do_train \
    --data_dir ${DatasetPath} \
    --task_name JD \
    --model_type lstm \
    --overwrite_output_dir \
    --output_dir "./outputs" \
    --num_train_epochs 100 \
    --learning_rate 2e-4 \
    --per_gpu_train_batch_size 64 \
    --per_gpu_eval_batch_size 64 \
    --logging_steps 10 \
    --overwrite_cache
