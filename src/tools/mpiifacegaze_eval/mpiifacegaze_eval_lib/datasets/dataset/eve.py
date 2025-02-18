from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import pycocotools.coco as coco
import numpy as np
import torch
import json
import os

import torch.utils.data as data

class EVE(data.Dataset):
  num_classes = 1
  default_resolution = [512, 512]
  mean = np.array([0.485, 0.456, 0.406],
                   dtype=np.float32).reshape(1, 1, 3)
  std  = np.array([0.229, 0.224, 0.225],
                   dtype=np.float32).reshape(1, 1, 3)
  
  mean = np.array([0.40789654, 0.44719302, 0.47026115],
                   dtype=np.float32).reshape(1, 1, 3)
  std  = np.array([0.28863828, 0.27408164, 0.27809835],
                   dtype=np.float32).reshape(1, 1, 3)
  
  # mean = np.array([1, 1, 1],
  #                  dtype=np.float32).reshape(1, 1, 3)
  # std  = np.array([1, 1, 1],
  #                  dtype=np.float32).reshape(1, 1, 3)

  def __init__(self, opt, split):
    super(EVE, self).__init__()
    self.data_dir = os.path.join(opt.data_dir, 'gaze_EVE_ffmpeg_ld')
    self.img_dir = os.path.join(self.data_dir, 'images')
    # self.img_dir = os.path.join(self.data_dir, 'images_himax_test_all')
    # _ann_name = {'train': f'train', 'val': f'val'}
    _ann_name = {'train': f'train', 'val': f'EVE_ld_ext_val'}
    # _ann_name = {'train': f'train', 'val': f'EVE_ld_s_val'}
    self.annot_path = os.path.join(
      self.data_dir, 'annotations', 
      'gaze_{}.json').format(_ann_name[split])
    self.max_objs = 1
    self.class_name = ['__background__', "gaze"]
    # self._valid_ids = np.arange(1, 21, dtype=np.int32)
    # self.cat_ids = {v: i for i, v in enumerate(self._valid_ids)}
    self.cat_ids = {1:0, 2:1}
    self._data_rng = np.random.RandomState(123)
    self._eig_val = np.array([0.2141788, 0.01817699, 0.00341571],
                             dtype=np.float32)
    self._eig_vec = np.array([
        [-0.58752847, -0.69563484, 0.41340352],
        [-0.5832747, 0.00994535, -0.81221408],
        [-0.56089297, 0.71832671, 0.41158938]
    ], dtype=np.float32)
    self.split = split
    self.opt = opt
    
    self.filtered_indices = []
    

    print('==> initializing EVE {} data.'.format(_ann_name[split]))
    self.coco = coco.COCO(self.annot_path)
    self.images = sorted(self.coco.getImgIds())
    self.num_samples = len(self.images)

    print('Loaded {} {} samples'.format(split, self.num_samples))

  def _to_float(self, x):
    return float("{:.2f}".format(x))

  def convert_eval_format(self, all_gp):
    detections = [[[] for __ in range(self.num_samples)] \
                  for _ in range(self.num_classes + 1)]
    for i in range(self.num_samples):
      img_id = self.images[i]
      for j in range(1, self.num_classes + 1):
        if isinstance(all_gp[img_id][j], np.ndarray):
          detections[j][i] = all_gp[img_id][j].tolist()
        else:
          detections[j][i] = all_gp[img_id][j]

    return detections

  def __len__(self):
    return self.num_samples

  def save_results(self, results, save_dir):
    json.dump(self.convert_eval_format(results), 
              open('{}/results.json'.format(save_dir), 'w'))


  def run_eval(self, results, save_dir):
    # result_json = os.path.join(save_dir, "results.json")
    # detections  = self.convert_eval_format(results)
    # json.dump(detections, open(result_json, "w"))

    self.save_results(results, save_dir)
    os.system('python tools/EVE_eval/evaluate.py ' + \
              '{}/results.json'.format(save_dir))
    
  def show_filter_data(self):

    return self.filtered_indices

