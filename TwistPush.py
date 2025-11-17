import maya.cmds as cmds


def create_twist_push(input_joint='jnt_l_ft_upperleg_0001', name='upperleg', num=5):
	token = input_joint.split('_')
	ori_side = token[1]
	region = token[2]
	desc = token[-2]
	index = token[-1]
	
	joints = []
	
	for side in ['l', 'r']:
		
		mult_matrix = cmds.createNode('multMatrix', n=f'multMatrix_{side}_{region}_{desc}Twist_0001')
		dec = cmds.createNode('decomposeMatrix', n=f'dec_{side}_{region}_{desc}Twist_0001')
		etq = cmds.createNode('eulerToQuat', n=f'etq_{side}_{region}_{desc}Twist_0001')
		qte = cmds.createNode('quatToEuler', n=f'qte_{side}_{region}_{desc}Twist_0001')
		
		jnt = input_joint.replace(f'_{ori_side}_', f'_{side}_')
		cmds.connectAttr(f'{jnt}.matrix', f'{mult_matrix}.matrixIn[0]')
		
		inv_node = cmds.createNode('inverseMatrix')
		matrix_sum = cmds.getAttr(f'{mult_matrix}.matrixSum')
		cmds.setAttr(f'{inv_node}.inputMatrix', matrix_sum, type='matrix')
		inv_mat = cmds.getAttr(f'{inv_node}.outputMatrix')
		cmds.setAttr(f'{mult_matrix}.matrixIn[1]', *inv_mat, type='matrix')
		cmds.delete(inv_node)
		
		cmds.connectAttr(f'{mult_matrix}.matrixSum', f'{dec}.inputMatrix')
		cmds.connectAttr(f'{dec}.outputRotate', f'{etq}.inputRotate')
		cmds.connectAttr(f'{etq}.outputQuat', f'{qte}.inputQuat')
		
		# Create remap and mult nodes
		for i in range(2, num + 1):
			curr_jnt = input_joint.replace(index, f'000{i}').replace(desc, f'{desc.lower()}Twist').replace(f'_{ori_side}_', f'_{side}_')
			
			mult = cmds.createNode('multiplyDivide', n=f'mult_{side}_{region}_{desc}Twist_000{i}_0001')
			
			for rmp_idx in range(1, 3):
				rmp = cmds.createNode('remapValue', n=f'rmp_{side}_{region}_{desc}Twist_000{i}_000{rmp_idx}')
				# Connect twist input — this may need to be changed to correct driving node
				cmds.connectAttr(f'{qte}.outputRotateX', f'{rmp}.inputValue')
				
				cmds.setAttr(f'{rmp}.outputMin', 1)
				cmds.setAttr(f'{rmp}.outputMax', 1.1)
				cmds.setAttr(f'{rmp}.inputMin', 0)
				
				if rmp_idx == 1:
					cmds.setAttr(f'{rmp}.inputMax', 90)
					cmds.connectAttr(f'{rmp}.outValue', f'{mult}.input1X')
					cmds.connectAttr(f'{rmp}.outValue', f'{mult}.input1Y')
					cmds.connectAttr(f'{rmp}.outValue', f'{mult}.input1Z')
				else:
					cmds.setAttr(f'{rmp}.inputMax', -90)
					cmds.connectAttr(f'{rmp}.outValue', f'{mult}.input2X')
					cmds.connectAttr(f'{rmp}.outValue', f'{mult}.input2Y')
					cmds.connectAttr(f'{rmp}.outValue', f'{mult}.input2Z')
			
			print(curr_jnt)
			cmds.connectAttr(f'{mult}.output', f'{curr_jnt}.scale')


create_twist_push(input_joint='jnt_l_ft_upperLeg_0001', name='upperleg', num=5)

#
#
# for i in range(6, 7):
# 	jnt = f'jnt_l_ft_upperlegTwist_000{i}'
# 	twist = f'jnt_c_spineTwist_000{i}'
#
# 	cmds.createNode('joint', n=twist, p=jnt)
# 	mult = cmds.createNode('multiplyDivide', n=f'mult_c_spineTwist_000{i}_0001')
#
# 	for index in range(1, 3):
#
# 		rmp = cmds.createNode('remapValue', n=f'rmp_c_spineTwist_000{i}_000{index}')
# 		cmds.connectAttr('qte_c_spineTwist_0001.outputRotateX', f'{rmp}.inputValue')
# 		cmds.setAttr(f'{rmp}.outputMin', 1)
# 		cmds.setAttr(f'{rmp}.outputMax', 1.5)
# 		cmds.setAttr(f'{rmp}.inputMin', 0)
#
# 		if index == 1:
# 			cmds.setAttr(f'{rmp}.inputMax', 90)
# 			cmds.connectAttr(f'{rmp}.outValue', f'{mult}.input1X')
# 			continue
# 		else:
# 			cmds.setAttr(f'{rmp}.inputMax', -90)
# 			cmds.connectAttr(f'{rmp}.outValue', f'{mult}.input2X')
#
# 		cmds.connectAttr(f'{mult}.outputX', f'{twist}.scaleZ')
