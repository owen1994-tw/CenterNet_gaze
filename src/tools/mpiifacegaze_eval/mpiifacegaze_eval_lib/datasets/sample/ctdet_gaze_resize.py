from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import torch.utils.data as data
import numpy as np
import torch
import json
import cv2
import os
from utils.image import flip, color_aug
from utils.image import get_affine_transform, affine_transform
from utils.image import gaussian_radius, draw_umich_gaussian, draw_msra_gaussian
from utils.image import draw_dense_reg
import math


def get_resize_affine_transform(src_ref_points, des_size):
    # des_size = (des_width, des_height)
    cv2.resize
    '''
    src_ref_points roi 
    (x0,y0)------------(x1,y1)
       |                  |
       |                  |
       |                  |
       |                  |
       |                  |
       |                  |
       |                  |
       |                  |
    (-,-)------------(x2, y2)
    '''
    src_points = [[src_ref_points[0], src_ref_points[1]], 
                  [src_ref_points[2], src_ref_points[1]], 
                  [src_ref_points[2], src_ref_points[3]]]
    src_points = np.array(src_points, dtype=np.float32)
              
    des_points = [[0, 0], [des_size[0], 0], [des_size[0], des_size[1]]]
    des_points = np.array(des_points, dtype=np.float32)
    
    print(src_points)
    print(des_points)

    trans = cv2.getAffineTransform(src_points, des_points)
    # des_img = cv2.warpAffine(src_img, trans, (des_width, des_height))

    return trans

class CTDet_gazeDataset(data.Dataset):
  def _get_border(self, border, size):
    i = 1
    while size - border // i <= border // i:
        i *= 2
    return border // i

  def __getitem__(self, index):
    img_id = self.images[index]
    file_name = self.coco.loadImgs(ids=[img_id])[0]['file_name']
    img_path = os.path.join(self.img_dir, file_name)
    ann_ids = self.coco.getAnnIds(imgIds=[img_id])
    anns = self.coco.loadAnns(ids=ann_ids)
    num_objs = min(len(anns), self.max_objs)
    

    img = cv2.imread(img_path)

    img_height, img_width = img.shape[0], img.shape[1]
    input_h, input_w = self.opt.input_h, self.opt.input_w
   
    
    flipped = False
    if self.split == 'train':
      # pass
      if np.random.random() < self.opt.flip:
        flipped = True
        img = img[:, ::-1, :]
        
    # img - src 
    # xmin ymin xmax ymax
    src_ref_points = [0, 0, img_width, img_height]
    trans_input = get_resize_affine_transform(src_ref_points, [input_w, input_h])
    inp = cv2.warpAffine(img, trans_input, 
                        (input_w, input_h),
                        flags=cv2.INTER_LINEAR)

    inp = (inp.astype(np.float32) / 255.)
    if self.split == 'train' and not self.opt.no_color_aug:
      color_aug(self._data_rng, inp, self._eig_val, self._eig_vec)
    inp = (inp - self.mean) / self.std
    inp = inp.transpose(2, 0, 1)

    output_h = input_h // self.opt.down_ratio
    output_w = input_w // self.opt.down_ratio
    
    print(f"output_hw: {output_h},{output_w}")

    num_classes = self.num_classes
  

    hm = np.zeros((num_classes, output_h, output_w), dtype=np.float32)
    reg = np.zeros((self.max_objs, 2), dtype=np.float32)
    ind = np.zeros((self.max_objs), dtype=np.int64)
    reg_mask = np.zeros((self.max_objs), dtype=np.uint8)
    face_grid = np.zeros((self.max_objs, 2), dtype=np.int64)

    draw_gaussian = draw_msra_gaussian if self.opt.mse_loss else \
                    draw_umich_gaussian
                    
      
      
    gt_det = []
    for k in range(num_objs):
      ann = anns[k]
      
      _,unit_pixel = ann["screenSize"]
      
      unit_pixel = eval(unit_pixel)
      sc_width, sc_height = unit_pixel  
      print("screenSize unit_pixel",f'{sc_height}, {sc_width}')
      sc = np.ones((1, sc_height, sc_width), dtype=np.float32)
     
      vp_height, vp_width = self.opt.vp_h, self.opt.vp_w
      vp = np.zeros((1, vp_height, vp_width), dtype=np.float32)
      vp = vp.transpose(1,2,0)
      
      
      x,y = ann['gazepoint']
      print("gazepoint",f'{x} {y}')
      if flipped:
        x = sc_width - x - 1
      
      ann_id = ann['id']
      print("id",f'{ann_id}')
      sc_gazepoint = np.array([x,y],dtype=np.int64)
      sc[0, sc_gazepoint[1]:sc_gazepoint[1]+20, sc_gazepoint[0]:sc_gazepoint[0]+20] = 20
      sc = sc.transpose(1,2,0)
      
      
      # ---- sc put into vp-------#
      large_shape = vp.shape
      small_shape = sc.shape

      large_mid = [s // 2 for s in large_shape]
      small_mid = [s // 2 for s in small_shape]
      offsets = [large_mid[i] - small_mid[i] for i in range(len(large_shape))]
      vp[offsets[0]:offsets[0] + small_shape[0], offsets[1]:offsets[1] + small_shape[1]] += sc

      # vp = vp.transpose(2,0,1)
      print(f"vp_with_sc: {vp.shape[0]},{vp.shape[1]}")
      
      vp_gazepoint_idx = np.where(vp == 20)
      print(vp_gazepoint_idx)
      
      vp_gazepoint = np.array([min(vp_gazepoint_idx[1]),min(vp_gazepoint_idx[0])])

      flipped = False
      if self.split == 'train':

        if np.random.random() < self.opt.flip:
          flipped = True
          vp = vp[:, ::-1, :]
          
        # vp - src    
        # xmin ymin xmax ymax
        src_ref_points = [0, 0, vp_width, vp_height]
        print(f"vp_height vp_width: {vp_height},{vp_width}")
        print(f"src_ref_points: {src_ref_points}")
        trans_vp2out = get_resize_affine_transform(src_ref_points, [output_w, output_h])
        vp_trans_out = cv2.warpAffine(vp, trans_vp2out, 
                (output_w, output_h),
                flags=cv2.INTER_LINEAR)

        print(f"vp_out: {vp_trans_out.shape[0]},{vp_trans_out.shape[1]}")
      
      
      cls_id = 0
      print(vp_gazepoint)
      vp_gazepoint_output = affine_transform(vp_gazepoint, trans_vp2out)
      h, w = self.opt.vp_heatmap_hw, self.opt.vp_heatmap_hw
      if h > 0 and w > 0:
        radius = gaussian_radius((math.ceil(h), math.ceil(w)))
        radius = max(0, int(radius))
        radius = self.opt.hm_gauss if self.opt.mse_loss else radius
        ct = np.array([ vp_gazepoint_output[0], vp_gazepoint_output[1]], dtype=np.float32)
        ct_int = ct.astype(np.int32)
        draw_gaussian(hm[cls_id], ct_int, radius)
        
        hm_gazepoint_idx = np.where(hm[cls_id] == 20)
        print(f"hm_gazepoint_idx: {hm_gazepoint_idx}")
        
        ind[k] = ct_int[1] * output_w + ct_int[0]
        reg[k] = ct - ct_int
        reg_mask[k] = 1
        face_grid[k] = 1
        print('---------------')
        print("ct",f'{ct}')
        print("ct_int",f'{ct_int}')
        print("reg[k]",f'{reg[k]}')
        print("radius",f'{radius}')

        gt_det.append([ct[1], ct[0], 1, cls_id])
        
    print("vp_trans_out.shape",f'{vp_trans_out.shape}') 
    print("ct_int",f'{ct_int}') 
    vp_trans_out[ct_int[1],ct_int[0]] = 1
    hm  = hm + vp_trans_out
    
    ret = {'input': inp, 'hm': hm, 'reg_mask': reg_mask, 'ind': ind, 'vp' : vp}
    if self.opt.reg_offset:
      ret.update({'reg': reg})
    if self.opt.face_grid:
      ret.update({'face_grid': face_grid})
    # if self.opt.debug > 0 or not self.split == 'train':
    #   gt_det = np.array(gt_det, dtype=np.float32) if len(gt_det) > 0 else \
    #            np.zeros((1, 4), dtype=np.float32)
    #   meta = {'c': c, 's': s, 'gt_det': gt_det, 'img_id': img_id}
    #   ret['meta'] = meta
    return ret