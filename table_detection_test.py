import cv2
import numpy as np

def detect_lines_improved(binary_image):
    """
    使用改进的形态学操作检测水平和垂直线条，并去除噪声
    """
    rows, cols = binary_image.shape
    
    # 检测水平线条
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (cols//10, 1))
    horizontal_lines = cv2.erode(binary_image, horizontal_kernel, iterations=2)
    horizontal_lines = cv2.dilate(horizontal_lines, horizontal_kernel, iterations=2)
    
    # 检测垂直线条
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, rows//10))
    vertical_lines = cv2.erode(binary_image, vertical_kernel, iterations=2)
    vertical_lines = cv2.dilate(vertical_lines, vertical_kernel, iterations=2)
    
    return horizontal_lines, vertical_lines

def get_line_coordinates_improved(lines_image, is_horizontal=True, min_gap=5):
    """
    从线条图像中提取线条坐标，并去除噪声
    """
    if is_horizontal:
        # 水平线：每行所有像素求和，白色线条处求和结果>0
        line_points = np.where(lines_image.sum(axis=1) > 0)[0]
    else:
        # 垂直线：每列所有像素求和，白色线条处求和结果>0
        line_points = np.where(lines_image.sum(axis=0) > 0)[0]
    
    if len(line_points) == 0:
        return []
    
    # 去重
    unique_points = np.unique(line_points)
    
    # 过滤噪声：只保留间隔大于min_gap像素的线条
    filtered_lines = [unique_points[0]]
    for point in unique_points[1:]:
        if point - filtered_lines[-1] > min_gap:
            filtered_lines.append(point)
    
    return filtered_lines

def detect_table_boundary_first(image_path):
    """
    首先检测整个表格的边界
    """
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图像: {image_path}")
        return None, None, None
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    
    # 找到最大轮廓作为表格边界
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print("未找到表格轮廓")
        return None, None, None
    
    table_contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(table_contour)
    
    # print(f"检测到表格边界: x={x}, y={y}, width={w}, height={h}")
    
    # 提取表格区域
    table_roi = binary[y:y+h, x:x+w]
    
    return image, table_roi, (x, y, w, h)

def crop_table_region(image, h_coords, v_coords, table_bbox, h_start=2, h_end=-1, v_start=0, v_end=7):
    """
    根据指定的线条索引裁剪表格区域
    """
    table_x, table_y, table_w, table_h = table_bbox
    
    # 检查索引是否有效
    if len(h_coords) <= max(h_start, h_end if h_end != -1 else 0):
        print(f"警告: 水平线数量不足 ({len(h_coords)} 条)，无法按指定索引裁剪")
        return None, None
    
    if len(v_coords) <= max(v_start, v_end):
        print(f"警告: 垂直线数量不足 ({len(v_coords)} 条)，无法按指定索引裁剪")
        return None, None
    
    # 确定裁剪边界（相对于表格区域的坐标）
    top_rel = h_coords[h_start]
    bottom_rel = h_coords[h_end] if h_end != -1 else h_coords[-1]
    left_rel = v_coords[v_start]
    right_rel = v_coords[v_end]
    
    # 转换为图像绝对坐标，下边和左边多留5像素边界
    top_abs = table_y + top_rel
    bottom_abs = table_y + bottom_rel + 15  # 下边多留5像素
    left_abs = table_x + left_rel - 5      # 左边多留5像素
    right_abs = table_x + right_rel
    
    # 边界检查，确保不超出图像范围
    img_height, img_width = image.shape[:2]
    left_abs = max(0, left_abs)                    # 左边界不能小于0
    top_abs = max(0, top_abs)                      # 上边界不能小于0
    right_abs = min(img_width, right_abs)          # 右边界不能超过图像宽度
    bottom_abs = min(img_height, bottom_abs)       # 下边界不能超过图像高度
    
    # print(f"裁剪区域:")
    # print(f"  水平线: 第{h_start+1}根 (y={top_abs}) 到 第{len(h_coords) if h_end==-1 else h_end+1}根 (y={bottom_abs})")
    # print(f"  垂直线: 第{v_start+1}根 (x={left_abs}) 到 第{v_end+1}根 (x={right_abs})")
    # print(f"  区域坐标: ({left_abs}, {top_abs}) 到 ({right_abs}, {bottom_abs})")
    
    # 裁剪图像
    cropped_image = image[top_abs:bottom_abs, left_abs:right_abs]
    crop_info = {
        'x': left_abs, 'y': top_abs, 
        'width': right_abs - left_abs, 'height': bottom_abs - top_abs,
        'h_start': h_start, 'h_end': h_end,
        'v_start': v_start, 'v_end': v_end
    }
    
    return cropped_image, crop_info

def detect_table_position_by_lines(image_path, crop_region=None):
    """
    通过改进的线条检测算法定位表格，并可选择裁剪特定区域
    """
    # 首先检测表格边界
    result = detect_table_boundary_first(image_path)
    if result[0] is None:
        return None
    
    image, table_roi, table_bbox = result
    table_x, table_y, table_w, table_h = table_bbox
    
    # 在表格区域内检测线条
    horizontal_lines, vertical_lines = detect_lines_improved(table_roi)
    
    # 获取线条坐标（相对于表格区域）
    h_coords = get_line_coordinates_improved(horizontal_lines, is_horizontal=True, min_gap=20)
    v_coords = get_line_coordinates_improved(vertical_lines, is_horizontal=False, min_gap=20)
    
    # print(f"检测到 {len(h_coords)} 条水平线: {h_coords}")
    # print(f"检测到 {len(v_coords)} 条垂直线: {v_coords}")
    
    if len(h_coords) < 2 or len(v_coords) < 2:
        print("检测到的线条数量不足，无法确定表格边界")
        return None
    
    # 绘制检测到的线条（在原图上）
    line_image = image.copy()
    
    # 绘制水平线并标注序号
    for i, y_rel in enumerate(h_coords):
        y_abs = table_y + y_rel
        color = (0, 255, 255)
        thickness = 1
        
        # 如果指定了裁剪区域，高亮目标线条
        if crop_region:
            if i == crop_region.get('h_start', -1) or i == (len(h_coords)-1 if crop_region.get('h_end', -1) == -1 else crop_region.get('h_end', -1)):
                color = (0, 255, 0)
                thickness = 2
        
        cv2.line(line_image, (table_x, y_abs), (table_x + table_w, y_abs), color, thickness)
        cv2.putText(line_image, f'H{i+1}', (table_x + 10, y_abs - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    # 绘制垂直线并标注序号
    for i, x_rel in enumerate(v_coords):
        x_abs = table_x + x_rel
        color = (255, 255, 0)
        thickness = 1
        
        # 如果指定了裁剪区域，高亮目标线条
        if crop_region:
            if i == crop_region.get('v_start', -1) or i == crop_region.get('v_end', -1):
                color = (0, 255, 0)
                thickness = 2
        
        cv2.line(line_image, (x_abs, table_y), (x_abs, table_y + table_h), color, thickness)
        cv2.putText(line_image, f'V{i+1}', (x_abs + 5, table_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    # 如果指定了裁剪区域
    cropped_image = None
    crop_info = None
    if crop_region:
        cropped_image, crop_info = crop_table_region(
            image, h_coords, v_coords, table_bbox,
            crop_region.get('h_start', 2),
            crop_region.get('h_end', -1),
            crop_region.get('v_start', 0),
            crop_region.get('v_end', 7)
        )
        
        if cropped_image is not None:
            # 在原图上绘制裁剪区域
            result_image = image.copy()
            cv2.rectangle(result_image, 
                         (crop_info['x'], crop_info['y']), 
                         (crop_info['x'] + crop_info['width'], crop_info['y'] + crop_info['height']), 
                         (0, 255, 0), 3)
            
            # print(f"裁剪区域尺寸: {crop_info['width']} x {crop_info['height']}")
            
            return result_image, line_image, cropped_image, crop_info
    
    # 如果没有裁剪，返回整个表格边界
    result_image = image.copy()
    cv2.rectangle(result_image, (table_x, table_y), (table_x + table_w, table_y + table_h), (0, 255, 0), 3)
    
    # print(f"完整表格位置: x={table_x}, y={table_y}, width={table_w}, height={table_h}")
    
    return result_image, line_image, None, table_bbox

def detect_table_position(image_path):
    """
    原始的轮廓检测方法（保留作为备选）
    """
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图像: {image_path}")
        return None
    
    # 转为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 二值化处理
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    
    # 1. 从二值图中找所有外层轮廓
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        print("未找到任何轮廓")
        return None
    
    # 2. 筛选出面积最大的轮廓（即表格外边框）
    table_contour = max(contours, key=cv2.contourArea)
    
    # 3. 计算轮廓的"轴对齐边界矩形"，得到表格坐标
    x, y, w, h = cv2.boundingRect(table_contour)
    
    # 绘制检测结果
    result_image = image.copy()
    cv2.rectangle(result_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
    
    # 打印结果
    print(f"表格位置: x={x}, y={y}, width={w}, height={h}")
    print(f"表格面积: {cv2.contourArea(table_contour)}")
    
    return result_image, (x, y, w, h)

def main():
    # 测试图像路径
    image_path = '/Volumes/1/场记单/WS3 SSR-D18场记单 20240509_lut_processed/WS3 SSR-D34场记单 20240525_page_007_lut_applied.jpg'
    
    # print("=== 使用改进的线条交点检测方法 ===")
    
    # 定义裁剪区域：从上到下第3根线到最后一根线，从左到右第1根到第8根线
    crop_region = {
        'h_start': 2,    # 第3根水平线 (索引从0开始)
        'h_end': -1,     # 最后一根水平线
        'v_start': 0,    # 第1根垂直线
        'v_end': 7       # 第8根垂直线
    }
    
    result = detect_table_position_by_lines(image_path, crop_region)
    
    if result is not None:
        if len(result) == 4:  # 包含裁剪结果
            result_image, line_image, cropped_image, crop_info = result
            

                
            # 只保存裁剪后的结果
            if cropped_image is not None:
                cv2.imwrite('cropped_table_region.jpg', cropped_image)
                print("裁剪的表格区域已保存为: cropped_table_region.jpg")
        
    else:
        print("线条检测失败，无法裁剪表格区域")

if __name__ == "__main__":
    main()