import { useState } from 'react'
import { Category, getCategories, createCategory, updateCategory, deleteCategory } from '@/lib/api'

export function useCategories() {
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(false)

  const fetchCategories = async () => {
    try {
      setLoading(true)
      const data = await getCategories()
      setCategories(data)
    } catch (error) {
      console.error('Failed to fetch categories:', error)
      throw error
    } finally {
      setLoading(false)
    }
  }

  const createNewCategory = async (category: Omit<Category, 'created_at' | 'updated_at' | 'created_by'> & { id?: string }) => {
    try {
      setLoading(true)
      const newCategory = await createCategory(category)
      await fetchCategories()
      return newCategory
    } catch (error) {
      console.error('Failed to create category:', error)
      throw error
    } finally {
      setLoading(false)
    }
  }

  const updateExistingCategory = async (id: string, category: Partial<Omit<Category, 'id' | 'created_at' | 'created_by'>>) => {
    try {
      setLoading(true)
      const updatedCategory = await updateCategory(id, category)
      await fetchCategories()
      return updatedCategory
    } catch (error) {
      console.error('Failed to update category:', error)
      throw error
    } finally {
      setLoading(false)
    }
  }

  const deleteExistingCategory = async (id: string) => {
    try {
      setLoading(true)
      await deleteCategory(id)
      await fetchCategories()
    } catch (error) {
      console.error('Failed to delete category:', error)
      throw error
    } finally {
      setLoading(false)
    }
  }

  return {
    categories,
    loading,
    fetchCategories,
    createCategory: createNewCategory,
    updateCategory: updateExistingCategory,
    deleteCategory: deleteExistingCategory
  }
}