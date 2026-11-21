# Backtests exploratorios

Esta carpeta guarda pruebas iniciales reproducibles para hipótesis que pasaron Gate A en [`../GATES.md`](../GATES.md). No se ejecutan backtests desde el workflow de Initial Research ni se promueven ideas automáticamente.

## Flujo

1. Completar y congelar `templates/backtest_preregistration.yaml` para una hipótesis específica.
2. Medir y registrar calidad/cobertura del dataset y las condiciones de ejecución. Con el inventario actual, los datos permanecen provisionales hasta completar esa revisión.
3. Obtener el veredicto `READY_FOR_EXPLORATORY_BACKTEST` en la revisión de viabilidad y guardar evidencia que respalde cada campo.
4. Crear un subdirectorio por ID de hipótesis y versión. Guardar configuración, código/notebook, manifiesto de datos, salidas y limitaciones.
5. Registrar resultado nulo, fallo o resultado adverso igual que uno favorable. No cambiar reglas en la misma versión después de ver resultados.

El backtest exploratorio permite revisar implementación y descartar. No basta para afirmar que hay un edge; eso requiere Gate C y una revisión posterior.
