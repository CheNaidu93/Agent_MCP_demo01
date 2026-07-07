import bisect  
a = [2, 4, 6, 8, 10]

# Linear search using 'in'
print(6 in a)       

# Linear search using 'count'
print(a.count(7) > 0)   

# Binary search using bisect
pos = bisect.bisect_left(a, 8)
print("Found at index:", pos)

li = [1,1,1,3,3,4,4,5,5,6,6]

print(bisect.bisect(li,1))
print(bisect.bisect_left(li,1))
print(bisect.bisect_right(li,1))
print('***************************************************')
print(bisect.bisect(li,4))
print(bisect.bisect_left(li,4))
print(bisect.bisect_right(li,4))
print('***************************************************')
print(bisect.bisect(li, 4))
print(bisect.bisect(li, 4, 0, 3))
print('***************************************************')
print(bisect.bisect_left(li, 4))
print(bisect.bisect_left(li, 5))
print('***************************************************')
nums = [5, 3, 8, 1]

# In-place sort
nums.sort()
print(nums)       

# New sorted list (descending)
print(sorted(nums, reverse=True))

print('***************************************************')
li = [1, 3, 4, 6]
bisect.insort(li, 5)
print(li)